import { SystemClock } from "../adapters/outbound/system/SystemClock";
import type { ObsidianVaultGateway } from "../adapters/outbound/vault";
import type { JobInfo } from "../application/dto/rag";
import type { Notifier } from "../application/ports/Notifier";
import type { RagGateway } from "../application/ports/RagGateway";
import type { SettingsRepository } from "../application/ports/SettingsRepository";
import { ActiveJobRegistry } from "../application/services/ActiveJobRegistry";
import { DocumentSyncState } from "../application/services/DocumentSyncState";
import { RequestReindex, type RequestReindexResult } from "../application/use-cases/RequestReindex";
import {
  SynchronizeVault,
  type SyncVaultProgress,
  type SyncVaultResult,
} from "../application/use-cases/SynchronizeVault";

export type WireIndexingDeps = {
  readonly vault: ObsidianVaultGateway;
  readonly rag: RagGateway;
  readonly settings: SettingsRepository;
  readonly notifier: Notifier;
};

export type IndexingProgressCallback = (progress: SyncVaultProgress) => void;
export type IndexingJobCallback = (job: JobInfo) => void;

export type WiredIndexing = {
  readonly syncState: DocumentSyncState;
  readonly jobRegistry: ActiveJobRegistry;
  readonly synchronizeVault: SynchronizeVault;
  readonly requestReindex: RequestReindex;
  readonly startInitialSync: (
    signal?: AbortSignal,
    onProgress?: IndexingProgressCallback,
  ) => Promise<SyncVaultResult>;
  readonly startReindex: (
    signal?: AbortSignal,
    onJobUpdate?: IndexingJobCallback,
  ) => Promise<RequestReindexResult>;
  readonly cancelActive: (signal?: AbortSignal) => Promise<JobInfo | null>;
  readonly dispose: () => void;
};

/**
 * Wires vault sync/reindex use cases and a shared ActiveJobRegistry for status UI.
 */
export function wireIndexing(deps: WireIndexingDeps): WiredIndexing {
  const clock = new SystemClock();
  const syncState = new DocumentSyncState();
  const jobRegistry = new ActiveJobRegistry();
  const synchronizeVault = new SynchronizeVault(
    deps.vault,
    deps.rag,
    deps.settings,
    syncState,
    deps.notifier,
    clock,
  );
  const requestReindex = new RequestReindex(deps.rag, deps.vault, deps.settings, syncState, clock);

  const startInitialSync = async (
    signal?: AbortSignal,
    onProgress?: IndexingProgressCallback,
  ): Promise<SyncVaultResult> => {
    try {
      return await synchronizeVault.execute(signal, {
        ...(onProgress ? { onProgress } : {}),
        onJobUpdate: (job) => {
          jobRegistry.set(job);
        },
      });
    } finally {
      jobRegistry.clear();
    }
  };

  const startReindex = async (
    signal?: AbortSignal,
    onJobUpdate?: IndexingJobCallback,
  ): Promise<RequestReindexResult> => {
    const result = await requestReindex.start(signal);
    jobRegistry.set(result.job);
    void requestReindex
      .watch((job) => {
        jobRegistry.set(job);
        onJobUpdate?.(job);
      }, signal)
      .finally(() => {
        jobRegistry.clear();
      });
    return result;
  };

  const cancelActive = async (signal?: AbortSignal): Promise<JobInfo | null> => {
    const fromSync = await synchronizeVault.cancel(signal);
    if (fromSync) {
      jobRegistry.clear();
      return fromSync;
    }
    const fromReindex = await requestReindex.cancel(signal);
    jobRegistry.clear();
    return fromReindex;
  };

  return {
    syncState,
    jobRegistry,
    synchronizeVault,
    requestReindex,
    startInitialSync,
    startReindex,
    cancelActive,
    dispose: () => {
      jobRegistry.clear();
    },
  };
}
