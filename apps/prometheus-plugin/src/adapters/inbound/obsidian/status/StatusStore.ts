import type { LlmModelChoice } from "../../../../application/use-cases/SelectLlmModel";
import type { SystemStatus } from "../../../../application/dto/system";
import type { SyncVaultProgress } from "../../../../application/use-cases/SynchronizeVault";
import type { JobInfo } from "../../../../application/dto/rag";
import {
  recommendedActionForIndex,
  type IndexRecommendedAction,
} from "../../../../domain/entities/IndexStatus";
import {
  recommendedActionForRuntime,
  type ManagedRuntimeState,
  type RuntimeRecommendedAction,
} from "../../../../domain/entities/RuntimeStatus";
import {
  isAbortError,
  RuntimeNotInstalledError,
  RuntimeVersionIncompatibleError,
} from "../../../../domain/errors";
import type { GetSystemStatus } from "../../../../application/use-cases/GetSystemStatus";
import type { InstallRuntime } from "../../../../application/use-cases/InstallRuntime";
import type { StartRuntime } from "../../../../application/use-cases/StartRuntime";
import type { StopRuntime } from "../../../../application/use-cases/StopRuntime";
import type { SelectLlmModel } from "../../../../application/use-cases/SelectLlmModel";
import { presentError } from "../errors/presentError";
import { estimateIndexingProgress, type IndexingProgressEstimate } from "./indexingProgress";

export type StatusViewState = {
  readonly status: SystemStatus | null;
  readonly runtimeAction: RuntimeRecommendedAction;
  readonly indexAction: IndexRecommendedAction;
  readonly models: readonly LlmModelChoice[];
  readonly actionBusy: boolean;
  readonly actionError: string | null;
  readonly indexingProgress: IndexingProgressEstimate | null;
  readonly installState: ManagedRuntimeState | null;
};

export type StatusStoreDeps = {
  readonly getSystemStatus: Pick<GetSystemStatus, "execute" | "poll">;
  readonly installRuntime: Pick<InstallRuntime, "execute">;
  readonly startRuntime: Pick<StartRuntime, "execute">;
  readonly stopRuntime: Pick<StopRuntime, "execute">;
  readonly selectLlmModel: Pick<SelectLlmModel, "list" | "select">;
  readonly startInitialSync: (
    signal?: AbortSignal,
    onProgress?: (progress: SyncVaultProgress) => void,
  ) => Promise<unknown>;
  readonly startReindex: (
    signal?: AbortSignal,
    onJobUpdate?: (job: JobInfo) => void,
  ) => Promise<unknown>;
  readonly cancelActive: (signal?: AbortSignal) => Promise<JobInfo | null>;
  readonly pollIntervalMs?: number;
};

type Listener = (state: StatusViewState) => void;

const IDLE_ACTIONS = {
  runtimeAction: "none" as const,
  indexAction: "none" as const,
};

export class StatusStore {
  private status: SystemStatus | null = null;
  private models: readonly LlmModelChoice[] = [];
  private actionBusy = false;
  private actionError: string | null = null;
  private indexingProgress: IndexingProgressEstimate | null = null;
  private installState: ManagedRuntimeState | null = null;
  private readonly listeners = new Set<Listener>();
  private pollController: AbortController | null = null;
  private actionController: AbortController | null = null;
  private disposed = false;
  private indexingStartedAtMs: number | null = null;
  private lastUploadTotal = 0;
  private readonly pollIntervalActiveMs: number;
  private readonly pollIntervalIdleMs: number;
  private activeUiViews = 0;
  private pollLoop: Promise<void> | null = null;
  private polling = false;

  constructor(private readonly deps: StatusStoreDeps) {
    this.pollIntervalActiveMs = deps.pollIntervalMs ?? 1_000;
    this.pollIntervalIdleMs = 15_000;
  }

  setActiveUiViews(count: number): void {
    this.activeUiViews = Math.max(0, count);
  }

  isPolling(): boolean {
    return this.polling;
  }

  startPolling(): void {
    if (this.disposed || this.polling) {
      return;
    }
    this.polling = true;
    this.pollController = new AbortController();
    this.pollLoop = this.runPollLoop(this.pollController.signal);
  }

  stopPolling(): void {
    if (!this.polling) {
      return;
    }
    this.polling = false;
    this.pollController?.abort();
    this.pollController = null;
    void this.pollLoop?.catch(() => undefined);
    this.pollLoop = null;
  }

  getState(): StatusViewState {
    const runtimeAction = this.status
      ? recommendedActionForRuntime(this.status.runtime.runtime)
      : IDLE_ACTIONS.runtimeAction;
    const indexAction = this.status
      ? recommendedActionForIndex(this.status.index)
      : IDLE_ACTIONS.indexAction;
    return {
      status: this.status,
      runtimeAction,
      indexAction,
      models: this.models,
      actionBusy: this.actionBusy,
      actionError: this.actionError,
      indexingProgress: this.indexingProgress,
      installState: this.installState,
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

  async installRuntime(): Promise<void> {
    await this.runAction(async (signal) => {
      this.installState = null;
      this.notify();
      await this.deps.installRuntime.execute((state) => {
        this.installState = state;
        this.notify();
      }, signal);
      const result = await this.deps.startRuntime.execute(signal);
      if (result.kind === "missing") {
        throw new RuntimeNotInstalledError();
      }
      if (result.kind === "incompatible" && result.runtime.kind === "incompatible") {
        throw new RuntimeVersionIncompatibleError(
          result.runtime.installedVersion,
          result.runtime.requiredRange,
        );
      }
      this.installState = null;
      await this.refresh(signal);
    });
  }

  async restartRuntime(): Promise<void> {
    await this.runAction(async (signal) => {
      await this.restartManagedRuntime(signal);
      await this.refresh(signal);
    });
  }

  async reindex(): Promise<void> {
    await this.runAction(async (signal) => {
      this.indexingStartedAtMs = Date.now();
      this.lastUploadTotal = 0;
      // Full vault rebuild via POST /reindex (force=true). Incremental sync cannot
      // proceed while the stored index fingerprint is incompatible.
      await this.deps.startReindex(signal, (job) => {
        const elapsedMs =
          this.indexingStartedAtMs === null ? 0 : Date.now() - this.indexingStartedAtMs;
        this.indexingProgress = estimateIndexingProgress({
          phase: "job",
          processed: 0,
          total: this.lastUploadTotal,
          jobProgress: job.progress,
          elapsedMs,
        });
        this.notify();
      });
      this.indexingProgress = null;
      this.indexingStartedAtMs = null;
      await this.refresh(signal);
    });
  }

  async cancelIndexing(): Promise<void> {
    this.actionController?.abort();
    try {
      await this.deps.cancelActive();
    } catch {
      // best-effort cancel
    }
    this.indexingProgress = null;
    this.indexingStartedAtMs = null;
    this.actionBusy = false;
    this.notify();
  }

  async refreshModels(): Promise<void> {
    await this.runAction(async (signal) => {
      this.models = await this.deps.selectLlmModel.list(signal);
    });
  }

  async selectModel(modelName: string): Promise<void> {
    await this.runAction(async (signal) => {
      const result = await this.deps.selectLlmModel.select(modelName, signal);
      this.models = await this.deps.selectLlmModel.list(signal);
      if (result.requiresRuntimeRestart) {
        await this.restartManagedRuntime(signal);
      }
      await this.refresh(signal);
    });
  }

  private async restartManagedRuntime(signal: AbortSignal): Promise<void> {
    await this.deps.stopRuntime.execute(signal);
    const result = await this.deps.startRuntime.execute(signal);
    if (result.kind === "missing") {
      throw new RuntimeNotInstalledError();
    }
    if (result.kind === "incompatible" && result.runtime.kind === "incompatible") {
      throw new RuntimeVersionIncompatibleError(
        result.runtime.installedVersion,
        result.runtime.requiredRange,
      );
    }
  }

  dispose(): void {
    if (this.disposed) {
      return;
    }
    this.disposed = true;
    this.stopPolling();
    this.actionController?.abort();
    this.listeners.clear();
  }

  private async runPollLoop(signal: AbortSignal): Promise<void> {
    try {
      while (!signal.aborted) {
        await this.refresh(signal);
        await sleepMs(this.resolvePollIntervalMs(), signal);
      }
    } catch (error) {
      if (!isAbortError(error)) {
        throw error;
      }
    }
  }

  private resolvePollIntervalMs(): number {
    const job = this.status?.activeJob;
    const indexing =
      job !== undefined && job !== null && (job.status === "pending" || job.status === "running");
    if (this.activeUiViews > 0 || indexing || this.actionBusy) {
      return this.pollIntervalActiveMs;
    }
    return this.pollIntervalIdleMs;
  }

  private async refresh(signal?: AbortSignal): Promise<void> {
    this.status = await this.deps.getSystemStatus.execute(
      signal ? { pollAllowed: true, signal } : { pollAllowed: true },
    );
    if (
      this.status.activeJob &&
      (this.status.activeJob.status === "pending" || this.status.activeJob.status === "running")
    ) {
      const elapsedMs =
        this.indexingStartedAtMs === null ? 0 : Date.now() - this.indexingStartedAtMs;
      this.indexingProgress = estimateIndexingProgress({
        phase: "job",
        processed: 0,
        total: this.lastUploadTotal,
        jobProgress: this.status.activeJob.progress,
        elapsedMs,
      });
    } else if (!this.actionBusy) {
      this.indexingProgress = null;
    }
    this.notify();
  }

  private async runAction(fn: (signal: AbortSignal) => Promise<void>): Promise<void> {
    if (this.disposed || this.actionBusy) {
      return;
    }
    this.actionController?.abort();
    const controller = new AbortController();
    this.actionController = controller;
    this.actionBusy = true;
    this.actionError = null;
    this.notify();
    try {
      await fn(controller.signal);
    } catch (error) {
      if (isAbortError(error) || controller.signal.aborted) {
        return;
      }
      this.installState = null;
      this.actionError = presentError(error).message;
    } finally {
      if (this.actionController === controller) {
        this.actionController = null;
        this.actionBusy = false;
        this.notify();
      }
    }
  }

  private notify(): void {
    const snapshot = this.getState();
    for (const listener of this.listeners) {
      listener(snapshot);
    }
  }
}

function sleepMs(ms: number, signal: AbortSignal): Promise<void> {
  if (signal.aborted) {
    return Promise.reject(new DOMException("The operation was aborted", "AbortError"));
  }
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = (): void => {
      window.clearTimeout(timer);
      signal.removeEventListener("abort", onAbort);
      reject(new DOMException("The operation was aborted", "AbortError"));
    };
    signal.addEventListener("abort", onAbort);
  });
}
