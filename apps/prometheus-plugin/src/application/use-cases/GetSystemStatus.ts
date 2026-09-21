import {
  IndexStatus,
  type IndexStatus as IndexStatusUnion,
} from "../../domain/entities/IndexStatus";
import {
  createRuntimeStatus,
  ManagedRuntimeState,
  OllamaState,
  type RuntimeStatus,
} from "../../domain/entities/RuntimeStatus";
import type { JobInfo, RuntimeServiceStatus } from "../dto/rag";
import type { SystemStatus } from "../dto/system";
import type { Clock } from "../ports/Clock";
import type { RagGateway } from "../ports/RagGateway";
import type { RuntimeGateway } from "../ports/RuntimeGateway";
import type { SettingsRepository } from "../ports/SettingsRepository";

export type GetSystemStatusInput = {
  readonly signal?: AbortSignal;
  /** When false, skip network poll (panel closed). */
  readonly pollAllowed?: boolean;
};

export type GetSystemStatusOptions = {
  readonly minIntervalMs?: number;
  readonly getActiveJob?: () => JobInfo | null;
};

export class GetSystemStatus {
  private lastResult: SystemStatus | null = null;
  private lastFetchedAtMs = 0;

  constructor(
    private readonly rag: RagGateway,
    private readonly runtime: RuntimeGateway,
    private readonly settings: SettingsRepository,
    private readonly clock: Clock,
    private readonly options: GetSystemStatusOptions = {},
  ) {}

  async execute(input: GetSystemStatusInput = {}): Promise<SystemStatus> {
    const pollAllowed = input.pollAllowed ?? true;
    const minIntervalMs = this.options.minIntervalMs ?? 1_000;
    const now = this.clock.now().getTime();

    if (!pollAllowed || (this.lastResult && now - this.lastFetchedAtMs < minIntervalMs)) {
      if (this.lastResult) {
        return this.lastResult;
      }
    }

    if (!pollAllowed) {
      return (
        this.lastResult ??
        this.degradedStatus(this.runtime.getProcessState(), null, this.clock.now())
      );
    }

    const settings = await this.settings.get();
    const processState = this.runtime.getProcessState();
    let service: RuntimeServiceStatus | null = null;
    try {
      service = await this.rag.status(input.signal);
    } catch {
      service = null;
    }

    const activeJob = this.options.getActiveJob?.() ?? null;
    const index = mapIndexStatus(service, activeJob);
    const ollama = service?.llmAvailable ? OllamaState.running() : OllamaState.stopped();
    const selectedModel = settings.llmModel
      ? {
          name: settings.llmModel,
          installed: service?.llmModel === settings.llmModel || service === null,
        }
      : null;

    const runtime: RuntimeStatus = createRuntimeStatus({
      runtime: processState,
      ollama,
      selectedModel,
    });

    const result: SystemStatus = {
      runtime,
      index,
      service,
      activeJob,
      fetchedAt: this.clock.now(),
    };
    this.lastResult = result;
    this.lastFetchedAtMs = result.fetchedAt.getTime();
    return result;
  }

  async poll(
    onUpdate: (status: SystemStatus) => void,
    signal?: AbortSignal,
    intervalMs = 1_000,
  ): Promise<void> {
    while (!signal?.aborted) {
      const status = await this.execute(
        signal ? { pollAllowed: true, signal } : { pollAllowed: true },
      );
      onUpdate(status);
      await this.clock.sleep(intervalMs, signal);
    }
  }

  private degradedStatus(
    processState: ReturnType<RuntimeGateway["getProcessState"]>,
    service: RuntimeServiceStatus | null,
    fetchedAt: Date,
  ): SystemStatus {
    return {
      runtime: createRuntimeStatus({
        runtime: processState.kind === "missing" ? ManagedRuntimeState.missing() : processState,
        ollama: OllamaState.stopped(),
        selectedModel: null,
      }),
      index: IndexStatus.notIndexed(),
      service,
      activeJob: null,
      fetchedAt,
    };
  }
}

function mapIndexStatus(
  service: RuntimeServiceStatus | null,
  activeJob: JobInfo | null,
): IndexStatusUnion {
  if (activeJob && (activeJob.status === "pending" || activeJob.status === "running")) {
    return IndexStatus.indexing(Math.round(activeJob.progress * 100));
  }
  if (!service) {
    return IndexStatus.notIndexed();
  }
  switch (service.indexState) {
    case "ready":
      return IndexStatus.ready({
        documentCount: service.documentCount,
        chunkCount: service.chunkCount,
        lastIndexedAt: service.lastIndexedAt,
        indexSizeBytes: service.indexSizeBytes,
      });
    case "rebuild_required":
      return IndexStatus.reindexRequired(service.reindexReason ?? "rebuild required");
    case "index_corrupted":
      return IndexStatus.corrupted(service.reindexReason ?? "index corrupted");
    case "not_indexed":
    default:
      return IndexStatus.notIndexed();
  }
}
