import type { ManagedRuntimeState } from "../../../../domain/entities/RuntimeStatus";
import type { LlmModelChoice } from "../../../../application/use-cases/SelectLlmModel";
import type { SyncVaultProgress } from "../../../../application/use-cases/SynchronizeVault";
import type { JobInfo } from "../../../../application/dto/rag";
import type { SystemStatus } from "../../../../application/dto/system";
import { isAbortError } from "../../../../domain/errors";
import {
  estimateIndexingProgress,
  type IndexingProgressEstimate,
} from "../status/indexingProgress";

export type OnboardingStepId = "install" | "ollama" | "model" | "index";

export type OnboardingStepStatus = "pending" | "running" | "success" | "error";

export type OnboardingStepState = {
  readonly id: OnboardingStepId;
  readonly status: OnboardingStepStatus;
  readonly message: string | null;
};

export type OnboardingState = {
  readonly steps: readonly OnboardingStepState[];
  readonly currentStep: OnboardingStepId;
  readonly models: readonly LlmModelChoice[];
  readonly selectedModel: string | null;
  readonly installState: ManagedRuntimeState | null;
  readonly indexingProgress: IndexingProgressEstimate | null;
  readonly completed: boolean;
};

export type OnboardingControllerDeps = {
  readonly installRuntime: (
    onState: (state: ManagedRuntimeState) => void,
    signal: AbortSignal,
  ) => Promise<void>;
  readonly startRuntime: (signal: AbortSignal) => Promise<void>;
  readonly getStatus: (signal: AbortSignal) => Promise<SystemStatus>;
  readonly listModels: (signal: AbortSignal) => Promise<readonly LlmModelChoice[]>;
  readonly selectModel: (name: string, signal: AbortSignal) => Promise<void>;
  readonly startInitialSync: (
    signal: AbortSignal,
    onProgress: (progress: SyncVaultProgress) => void,
  ) => Promise<unknown>;
  readonly cancelActive: (signal?: AbortSignal) => Promise<JobInfo | null>;
  readonly markCompleted: () => Promise<void>;
};

type Listener = (state: OnboardingState) => void;

const STEP_ORDER: readonly OnboardingStepId[] = ["install", "ollama", "model", "index"];

export class OnboardingController {
  private readonly steps: OnboardingStepState[] = STEP_ORDER.map((id) => ({
    id,
    status: "pending",
    message: null,
  }));
  private currentStep: OnboardingStepId = "install";
  private models: readonly LlmModelChoice[] = [];
  private selectedModel: string | null = null;
  private installState: ManagedRuntimeState | null = null;
  private indexingProgress: IndexingProgressEstimate | null = null;
  private completed = false;
  private readonly listeners = new Set<Listener>();
  private actionController: AbortController | null = null;
  private disposed = false;
  private indexingStartedAtMs: number | null = null;
  private lastUploadTotal = 0;

  constructor(private readonly deps: OnboardingControllerDeps) {}

  getState(): OnboardingState {
    return {
      steps: this.steps.map((step) => ({ ...step })),
      currentStep: this.currentStep,
      models: this.models,
      selectedModel: this.selectedModel,
      installState: this.installState,
      indexingProgress: this.indexingProgress,
      completed: this.completed,
    };
  }

  subscribe(listener: Listener): () => void {
    if (this.disposed) {
      return () => undefined;
    }
    this.listeners.add(listener);
    listener(this.getState());
    return () => {
      this.listeners.delete(listener);
    };
  }

  async runCurrentStep(): Promise<void> {
    switch (this.currentStep) {
      case "install":
        await this.runInstall();
        break;
      case "ollama":
        await this.runOllamaCheck();
        break;
      case "model":
        await this.runLoadModels();
        break;
      case "index":
        await this.runIndex();
        break;
      default: {
        const _exhaustive: never = this.currentStep;
        return _exhaustive;
      }
    }
  }

  async selectModel(name: string): Promise<void> {
    await this.withAction("model", async (signal) => {
      await this.deps.selectModel(name, signal);
      this.selectedModel = name;
      this.setStep("model", "success", `Selected ${name}`);
      this.advanceTo("index");
    });
  }

  async cancelIndexing(): Promise<void> {
    this.actionController?.abort();
    try {
      await this.deps.cancelActive();
    } catch {
      // best-effort
    }
    this.indexingProgress = null;
    this.setStep("index", "error", "Indexing cancelled");
    this.notify();
  }

  async finish(): Promise<void> {
    if (this.completed) {
      return;
    }
    await this.deps.markCompleted();
    this.completed = true;
    this.notify();
  }

  dispose(): void {
    if (this.disposed) {
      return;
    }
    this.disposed = true;
    this.actionController?.abort();
    this.listeners.clear();
  }

  private async runInstall(): Promise<void> {
    await this.withAction("install", async (signal) => {
      this.installState = null;
      await this.deps.installRuntime((state) => {
        this.installState = state;
        this.notify();
      }, signal);
      await this.deps.startRuntime(signal);
      this.installState = null;
      this.setStep("install", "success", "Runtime installed and running");
      this.advanceTo("ollama");
    });
  }

  private async runOllamaCheck(): Promise<void> {
    await this.withAction("ollama", async (signal) => {
      const status = await this.deps.getStatus(signal);
      if (status.runtime.ollama.kind === "running") {
        this.setStep("ollama", "success", "Ollama is running");
        this.advanceTo("model");
        return;
      }
      if (status.runtime.ollama.kind === "notInstalled") {
        this.setStep(
          "ollama",
          "error",
          "Ollama is not installed. Install it from https://ollama.com, then retry.",
        );
        return;
      }
      this.setStep("ollama", "error", "Ollama is stopped. Start Ollama, then retry.");
    });
  }

  private async runLoadModels(): Promise<void> {
    await this.withAction("model", async (signal) => {
      this.models = await this.deps.listModels(signal);
      if (this.models.length === 0) {
        this.setStep(
          "model",
          "error",
          "No local models found. Download a model with Ollama, then retry.",
        );
        return;
      }
      this.setStep("model", "pending", "Select a local model to continue");
      this.notify();
    });
  }

  private async runIndex(): Promise<void> {
    await this.withAction("index", async (signal) => {
      this.indexingStartedAtMs = Date.now();
      this.lastUploadTotal = 0;
      await this.deps.startInitialSync(signal, (progress) => {
        if (progress.total > 0) {
          this.lastUploadTotal = progress.total;
        }
        const elapsedMs =
          this.indexingStartedAtMs === null ? 0 : Date.now() - this.indexingStartedAtMs;
        this.indexingProgress = estimateIndexingProgress({
          phase: progress.phase,
          processed: progress.processed,
          total: progress.total > 0 ? progress.total : this.lastUploadTotal,
          jobProgress: progress.phase === "reconciling" ? 0.5 : 0,
          elapsedMs,
        });
        this.notify();
      });
      this.indexingProgress = null;
      this.setStep("index", "success", "Vault indexed");
      await this.finish();
    });
  }

  private async withAction(
    step: OnboardingStepId,
    fn: (signal: AbortSignal) => Promise<void>,
  ): Promise<void> {
    if (this.disposed) {
      return;
    }
    this.actionController?.abort();
    const controller = new AbortController();
    this.actionController = controller;
    this.currentStep = step;
    this.setStep(step, "running", null);
    try {
      await fn(controller.signal);
    } catch (error) {
      if (isAbortError(error) || controller.signal.aborted) {
        return;
      }
      this.setStep(step, "error", error instanceof Error ? error.message : "Step failed");
    } finally {
      if (this.actionController === controller) {
        this.actionController = null;
      }
    }
  }

  private advanceTo(step: OnboardingStepId): void {
    this.currentStep = step;
    this.notify();
  }

  private setStep(
    id: OnboardingStepId,
    status: OnboardingStepStatus,
    message: string | null,
  ): void {
    const index = this.steps.findIndex((step) => step.id === id);
    if (index < 0) {
      return;
    }
    this.steps[index] = { id, status, message };
    this.notify();
  }

  private notify(): void {
    const snapshot = this.getState();
    for (const listener of this.listeners) {
      listener(snapshot);
    }
  }
}

export const ONBOARDING_STEP_TITLES: Record<OnboardingStepId, string> = {
  install: "Download Prometheus Runtime",
  ollama: "Check Ollama",
  model: "Select local LLM",
  index: "Index your vault",
};
