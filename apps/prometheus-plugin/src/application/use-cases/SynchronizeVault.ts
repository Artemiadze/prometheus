import type { JobInfo, VaultSnapshotEntry } from "../dto/rag";
import type { Clock } from "../ports/Clock";
import type { Notifier } from "../ports/Notifier";
import type { RagGateway } from "../ports/RagGateway";
import type { SettingsRepository } from "../ports/SettingsRepository";
import type { VaultGateway } from "../ports/VaultGateway";
import { computeContentHash } from "../services/contentHash";
import type { DocumentSyncState } from "../services/DocumentSyncState";
import { JobTracker } from "../services/JobTracker";
import { isIgnoredPath, requireVaultId } from "../services/settingsHelpers";

export type SyncVaultPhase = "scanning" | "uploading" | "reconciling" | "completed";

export type SyncVaultProgress = {
  readonly phase: SyncVaultPhase;
  readonly processed: number;
  readonly total: number;
};

export type SyncVaultFileFailure = {
  readonly path: string;
  readonly message: string;
};

export type SyncVaultResult = {
  readonly job: JobInfo;
  readonly failures: readonly SyncVaultFileFailure[];
};

export type SynchronizeVaultOptions = {
  readonly batchSize?: number;
  readonly onProgress?: (progress: SyncVaultProgress) => void;
};

export class SynchronizeVault {
  private readonly jobs: JobTracker;

  constructor(
    private readonly vault: VaultGateway,
    private readonly rag: RagGateway,
    private readonly settings: SettingsRepository,
    private readonly syncState: DocumentSyncState,
    private readonly notifier: Notifier,
    clock: Clock,
  ) {
    this.jobs = new JobTracker(rag, clock);
  }

  async execute(
    signal?: AbortSignal,
    options: SynchronizeVaultOptions = {},
  ): Promise<SyncVaultResult> {
    const settings = await this.settings.get();
    const vaultId = requireVaultId(settings);
    const batchSize = options.batchSize ?? 50;

    options.onProgress?.({ phase: "scanning", processed: 0, total: 0 });
    const snapshot = await this.vault.getVaultSnapshot(signal);
    const files = snapshot.filter(
      (file) => !isIgnoredPath(file.path.value, settings.ignoredFolders),
    );

    const failures: SyncVaultFileFailure[] = [];
    const entries: VaultSnapshotEntry[] = [];
    let processed = 0;

    for (let i = 0; i < files.length; i += batchSize) {
      const batch = files.slice(i, i + batchSize);
      for (const file of batch) {
        const contentHash = computeContentHash(file.content);
        const documentId = this.syncState.resolveOrCreate(file.path);
        const existing = this.syncState.getByPath(file.path);
        const unchanged = existing?.contentHash === contentHash;
        const revision = unchanged
          ? (existing?.revision ?? 1)
          : this.syncState.nextRevision(file.path);

        if (!unchanged) {
          options.onProgress?.({
            phase: "uploading",
            processed,
            total: files.length,
          });
          try {
            await this.rag.upsertDocument(
              vaultId,
              documentId,
              {
                path: file.path,
                content: file.content,
                revision,
                modifiedAt: file.modifiedAt,
              },
              signal,
            );
            this.syncState.upsert({
              documentId,
              path: file.path,
              contentHash,
              revision,
            });
          } catch (error) {
            const message = error instanceof Error ? error.message : "upsert failed";
            failures.push({ path: file.path.value, message });
            this.notifier.warning(`Failed to index ${file.path.value}`);
          }
        } else if (existing) {
          this.syncState.upsert(existing);
        }

        entries.push({
          documentId,
          path: file.path,
          contentHash,
          revision,
          modifiedAt: file.modifiedAt,
        });
        processed += 1;
      }
      // Yield between batches so large vaults do not block the event loop.
      await Promise.resolve();
    }

    options.onProgress?.({
      phase: "reconciling",
      processed: files.length,
      total: files.length,
    });
    const started = await this.rag.syncComplete(vaultId, entries, signal);
    const job = await this.jobs.watch(started.jobId, undefined, signal);
    options.onProgress?.({
      phase: "completed",
      processed: files.length,
      total: files.length,
    });
    return { job, failures };
  }
}
