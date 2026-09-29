import type {
  NetworkAccessMode,
  PluginSettings,
  RuntimeMode,
} from "../../../../application/dto/settings";
import type { JobInfo, RuntimeServiceStatus } from "../../../../application/dto/rag";
import type { Notifier } from "../../../../application/ports/Notifier";
import type { RuntimeGateway } from "../../../../application/ports/RuntimeGateway";
import type { SettingsRepository } from "../../../../application/ports/SettingsRepository";
import type { ApplyIgnoredFolderChange } from "../../../../application/services/ApplyIgnoredFolderChange";
import type { InstallRuntime } from "../../../../application/use-cases/InstallRuntime";
import type {
  LlmModelChoice,
  SelectLlmModel,
} from "../../../../application/use-cases/SelectLlmModel";
import type { StartRuntime } from "../../../../application/use-cases/StartRuntime";
import type { StopRuntime } from "../../../../application/use-cases/StopRuntime";
import type { ManagedRuntimeState } from "../../../../domain/entities/RuntimeStatus";
import { isAbortError } from "../../../../domain/errors";
import type { StatusStore, StatusViewState } from "../status/StatusStore";
import { presentError } from "../errors/presentError";
import { validateIgnoredFolderPath } from "./folderValidation";
import { isUpdateAvailable } from "./runtimeUpdateCheck";

export type SettingsViewState = {
  readonly settings: PluginSettings;
  readonly models: readonly LlmModelChoice[];
  readonly runtimeState: ManagedRuntimeState | null;
  readonly service: RuntimeServiceStatus | null;
  readonly dataRootPath: string;
  readonly actionBusy: boolean;
  readonly actionError: string | null;
  readonly chunkReindexWarning: boolean;
  readonly updateAvailable: boolean;
  readonly ready: boolean;
};

export type SettingsControllerDeps = {
  readonly settings: SettingsRepository;
  readonly notifier: Notifier;
  readonly runtimeGateway: RuntimeGateway;
  readonly installRuntime: Pick<InstallRuntime, "execute">;
  readonly startRuntime: Pick<StartRuntime, "execute">;
  readonly stopRuntime: Pick<StopRuntime, "execute">;
  readonly selectLlmModel: Pick<SelectLlmModel, "list" | "select">;
  readonly applyIgnoredFolderChange: Pick<ApplyIgnoredFolderChange, "execute">;
  readonly startReindex: (
    signal?: AbortSignal,
    onJobUpdate?: (job: JobInfo) => void,
  ) => Promise<unknown>;
  readonly statusStore: Pick<StatusStore, "subscribe" | "getState">;
  readonly autoIndexing: {
    setEnabled: (enabled: boolean) => void;
    updateDebounce: (options: { debounceMs?: number; maxConcurrent?: number }) => void;
  };
  readonly folderExists: (path: string) => boolean;
  readonly bundledReleaseVersion: string;
  readonly setVerboseLogging?: (enabled: boolean) => void;
  readonly openDiagnostics?: () => void;
  readonly onActivated?: () => void;
};

type Listener = (state: SettingsViewState) => void;

export class SettingsController {
  private settings: PluginSettings | null = null;
  private models: readonly LlmModelChoice[] = [];
  private runtimeState: ManagedRuntimeState | null = null;
  private service: RuntimeServiceStatus | null = null;
  private actionBusy = false;
  private actionError: string | null = null;
  private chunkReindexWarning = false;
  private readonly listeners = new Set<Listener>();
  private actionController: AbortController | null = null;
  private disposed = false;
  private readonly unsubscribeStatus: () => void;
  private readonly dataRootPath: string;
  private readonly bundledReleaseVersion: string;
  private readyPromise: Promise<void>;

  constructor(private readonly deps: SettingsControllerDeps) {
    this.dataRootPath = deps.runtimeGateway.getDataRootPath();
    this.bundledReleaseVersion = deps.bundledReleaseVersion;
    this.unsubscribeStatus = deps.statusStore.subscribe((state) => {
      this.applyStatus(state);
    });
    this.readyPromise = this.bootstrap();
  }

  getState(): SettingsViewState {
    const settings = this.settings ?? fallbackSettings();
    const installedVersion =
      this.runtimeState?.kind === "running"
        ? this.runtimeState.version
        : this.runtimeState?.kind === "incompatible"
          ? this.runtimeState.installedVersion
          : null;
    const updateAvailable =
      this.runtimeState?.kind === "incompatible" ||
      isUpdateAvailable(installedVersion, this.bundledReleaseVersion);
    return {
      settings,
      models: this.models,
      runtimeState: this.runtimeState,
      service: this.service,
      dataRootPath: this.dataRootPath,
      actionBusy: this.actionBusy,
      actionError: this.actionError,
      chunkReindexWarning: this.chunkReindexWarning,
      updateAvailable,
      ready: this.settings !== null,
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

  async updateRuntimeMode(mode: RuntimeMode): Promise<void> {
    await this.patchSettings({ runtimeMode: mode });
  }

  async updateCustomBinaryPath(path: string): Promise<void> {
    await this.readyPromise;
    if (!this.settings) {
      return;
    }
    const previous = this.settings.customBinaryPath;
    const trimmed = path.trim();
    const nextPath = trimmed.length > 0 ? trimmed : null;
    await this.patchSettings({ customBinaryPath: nextPath, runtimeMode: "custom" });
    if (nextPath) {
      const located = await this.deps.runtimeGateway.locate();
      if (located.kind !== "custom") {
        await this.patchSettings({ customBinaryPath: previous });
        this.deps.notifier.warning("Custom path is not a valid executable.");
        this.actionError = "Custom path is not a valid executable.";
        this.notify();
      }
    }
  }

  async installOrUpdateRuntime(): Promise<void> {
    await this.runAction(async (signal) => {
      await this.deps.installRuntime.execute(undefined, signal);
      await this.deps.startRuntime.execute(signal);
      this.deps.onActivated?.();
    });
  }

  async restartRuntime(): Promise<void> {
    await this.runAction(async (signal) => {
      await this.deps.stopRuntime.execute(signal);
      await this.deps.startRuntime.execute(signal);
      this.deps.onActivated?.();
    });
  }

  async setAutoIndexing(enabled: boolean): Promise<void> {
    await this.patchSettings({ autoIndexing: enabled });
    this.deps.autoIndexing.setEnabled(enabled);
  }

  async addIgnoredFolder(rawPath: string): Promise<void> {
    await this.readyPromise;
    if (!this.settings) {
      return;
    }
    const validated = validateIgnoredFolderPath(rawPath, this.deps.folderExists);
    if (!validated.ok) {
      this.deps.notifier.warning(validated.message);
      this.actionError = validated.message;
      this.notify();
      return;
    }
    if (this.settings.ignoredFolders.includes(validated.normalized)) {
      return;
    }
    const previous = this.settings.ignoredFolders;
    const next = [...previous, validated.normalized];
    await this.patchSettings({ ignoredFolders: next });
    const removed = await this.deps.applyIgnoredFolderChange.execute({
      previousIgnoredFolders: previous,
      nextIgnoredFolders: next,
    });
    if (removed > 0) {
      this.deps.notifier.info(`Removed ${removed} document(s) from the index.`);
    }
  }

  async removeIgnoredFolder(path: string): Promise<void> {
    await this.readyPromise;
    if (!this.settings) {
      return;
    }
    const previous = this.settings.ignoredFolders;
    const next = previous.filter((folder) => folder !== path);
    if (next.length === previous.length) {
      return;
    }
    await this.patchSettings({ ignoredFolders: next });
    await this.deps.applyIgnoredFolderChange.execute({
      previousIgnoredFolders: previous,
      nextIgnoredFolders: next,
    });
  }

  async setChunkSize(tokens: number): Promise<void> {
    if (!Number.isInteger(tokens) || tokens <= 0) {
      this.deps.notifier.warning("Chunk size must be a positive integer.");
      return;
    }
    this.chunkReindexWarning = true;
    await this.patchSettings({ chunkSizeTokens: tokens });
  }

  async setChunkOverlap(tokens: number): Promise<void> {
    if (!Number.isInteger(tokens) || tokens < 0) {
      this.deps.notifier.warning("Chunk overlap must be a non-negative integer.");
      return;
    }
    this.chunkReindexWarning = true;
    await this.patchSettings({ chunkOverlapTokens: tokens });
  }

  async triggerReindex(): Promise<void> {
    await this.runAction(async (signal) => {
      await this.deps.startReindex(signal);
      this.chunkReindexWarning = false;
    });
  }

  async refreshModels(): Promise<void> {
    await this.runAction(async (signal) => {
      this.models = await this.deps.selectLlmModel.list(signal);
    });
  }

  async selectModel(name: string): Promise<void> {
    await this.runAction(async (signal) => {
      const result = await this.deps.selectLlmModel.select(name, signal);
      this.models = result.models;
      if (this.settings) {
        this.settings = { ...this.settings, llmModel: result.selected };
      }
      if (result.requiresRuntimeRestart) {
        this.deps.notifier.info("Model updated. Restart the runtime if the change does not apply.");
      }
    });
  }

  async updateOllamaAddress(address: string): Promise<void> {
    const trimmed = address.trim();
    if (!isValidOllamaAddress(trimmed)) {
      this.deps.notifier.warning("Ollama address must look like host:port (e.g. 127.0.0.1:11434).");
      this.actionError = "Invalid Ollama address.";
      this.notify();
      return;
    }
    await this.patchSettings({ ollamaAddress: trimmed });
  }

  async setTemperature(value: number): Promise<void> {
    if (!Number.isFinite(value) || value < 0 || value > 2) {
      this.deps.notifier.warning("Temperature must be between 0 and 2.");
      return;
    }
    await this.patchSettings({ llmTemperature: value });
  }

  async setContextSize(value: number): Promise<void> {
    if (!Number.isInteger(value) || value <= 0) {
      this.deps.notifier.warning("Context size must be a positive integer.");
      return;
    }
    await this.patchSettings({ llmContextSize: value });
  }

  async setNetworkAccess(mode: NetworkAccessMode): Promise<void> {
    await this.patchSettings({ networkAccess: mode });
  }

  async setVerboseLogging(enabled: boolean): Promise<void> {
    await this.patchSettings({ verboseLogging: enabled });
    this.deps.setVerboseLogging?.(enabled);
  }

  async setRuntimeAutostart(enabled: boolean): Promise<void> {
    await this.patchSettings({ runtimeAutostart: enabled });
  }

  openDiagnostics(): void {
    this.deps.openDiagnostics?.();
  }

  dispose(): void {
    if (this.disposed) {
      return;
    }
    this.disposed = true;
    this.unsubscribeStatus();
    this.actionController?.abort();
    this.listeners.clear();
  }

  private async bootstrap(): Promise<void> {
    this.settings = await this.deps.settings.get();
    this.applyStatus(this.deps.statusStore.getState());
    this.notify();
  }

  private applyStatus(state: StatusViewState): void {
    const nextRuntime = state.status?.runtime.runtime ?? null;
    const nextService = state.status?.service ?? null;
    if (
      runtimeStatesEqual(this.runtimeState, nextRuntime) &&
      servicesEqual(this.service, nextService)
    ) {
      return;
    }
    this.runtimeState = nextRuntime;
    this.service = nextService;
    this.notify();
  }

  private async patchSettings(partial: Partial<PluginSettings>): Promise<void> {
    await this.readyPromise;
    if (!this.settings || this.disposed) {
      return;
    }
    const next = { ...this.settings, ...partial };
    await this.deps.settings.save(next);
    this.settings = next;
    this.actionError = null;
    this.notify();
  }

  private async runAction(fn: (signal: AbortSignal) => Promise<void>): Promise<void> {
    await this.readyPromise;
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
      this.actionError = presentError(error).message;
      this.deps.notifier.error(this.actionError);
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

function isValidOllamaAddress(value: string): boolean {
  return /^[A-Za-z0-9.-]+:\d{1,5}$/.test(value);
}

function runtimeStatesEqual(
  left: ManagedRuntimeState | null,
  right: ManagedRuntimeState | null,
): boolean {
  if (left === right) {
    return true;
  }
  if (!left || !right || left.kind !== right.kind) {
    return false;
  }
  switch (left.kind) {
    case "running":
      return right.kind === "running" && left.version === right.version;
    case "downloading":
      return right.kind === "downloading" && left.progressPercent === right.progressPercent;
    case "incompatible":
      return (
        right.kind === "incompatible" &&
        left.installedVersion === right.installedVersion &&
        left.requiredRange === right.requiredRange
      );
    case "stopped":
      return right.kind === "stopped" && left.reason === right.reason;
    default:
      return true;
  }
}

function servicesEqual(
  left: RuntimeServiceStatus | null,
  right: RuntimeServiceStatus | null,
): boolean {
  if (left === right) {
    return true;
  }
  if (!left || !right) {
    return false;
  }
  return (
    left.runtimeVersion === right.runtimeVersion &&
    left.indexSizeBytes === right.indexSizeBytes &&
    left.documentCount === right.documentCount &&
    left.chunkCount === right.chunkCount &&
    left.indexState === right.indexState &&
    left.llmModel === right.llmModel
  );
}

function fallbackSettings(): PluginSettings {
  return {
    runtimeMode: "managed",
    customBinaryPath: null,
    autoIndexing: true,
    ignoredFolders: [],
    llmModel: "",
    ollamaAddress: "127.0.0.1:11434",
    networkAccess: "updates_only",
    vaultId: null,
    noteOpenMode: "reuse_active",
    indexingDebounceMs: 750,
    maxConcurrentSyncs: 2,
    searchScopeMode: "entire_vault",
    applySearchScopeToChat: false,
    hasCompletedOnboarding: false,
    chunkSizeTokens: 700,
    chunkOverlapTokens: 80,
    llmTemperature: 0.2,
    llmContextSize: 4096,
    verboseLogging: false,
    runtimeAutostart: false,
  };
}
