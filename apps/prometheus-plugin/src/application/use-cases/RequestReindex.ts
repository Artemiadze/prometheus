import type { JobInfo, ReindexDocumentInput } from "../dto/rag";
import type { VaultId } from "../../domain/value-objects/VaultId";
import type { Clock } from "../ports/Clock";
import type { RagGateway } from "../ports/RagGateway";
import type { SettingsRepository } from "../ports/SettingsRepository";
import type { VaultGateway } from "../ports/VaultGateway";
import { computeContentHash } from "../services/contentHash";
import type { DocumentSyncState } from "../services/DocumentSyncState";
import { JobTracker } from "../services/JobTracker";
import {
  effectiveIgnoredFolders,
  isIgnoredPath,
  requireVaultId,
} from "../services/settingsHelpers";

export type RequestReindexResult =
  | {
      readonly kind: "started";
      readonly job: JobInfo;
      readonly reindexRequired: boolean;
      readonly reindexReason: string | null;
    }
  | {
      readonly kind: "already_running";
      readonly job: JobInfo;
      readonly reindexRequired: boolean;
      readonly reindexReason: string | null;
    };

export class RequestReindex {
  private activeJobId: string | null = null;
  private readonly jobs: JobTracker;

  constructor(
    private readonly rag: RagGateway,
    private readonly vault: VaultGateway,
    private readonly settings: SettingsRepository,
    private readonly syncState: DocumentSyncState,
    clock: Clock,
  ) {
    this.jobs = new JobTracker(rag, clock);
  }

  async start(signal?: AbortSignal): Promise<RequestReindexResult> {
    const settings = await this.settings.get();
    const vaultId = requireVaultId(settings);
    const status = await this.safeStatus(vaultId, signal);

    if (this.activeJobId) {
      const existing = await this.rag.getJob(this.activeJobId, signal);
      if (existing.status === "pending" || existing.status === "running") {
        return {
          kind: "already_running",
          job: existing,
          reindexRequired: status?.reindexRequired ?? false,
          reindexReason: status?.reindexReason ?? null,
        };
      }
    }

    const ignored = effectiveIgnoredFolders(settings);
    const snapshot = await this.vault.getVaultSnapshot(signal, ignored);
    const documents: ReindexDocumentInput[] = [];

    for (const file of snapshot) {
      if (isIgnoredPath(file.path.value, ignored)) {
        continue;
      }
      const documentId = this.syncState.resolveOrCreate(file.path);
      const contentHash = computeContentHash(file.content);
      const revision = this.syncState.nextRevision(file.path);
      documents.push({
        documentId,
        path: file.path,
        content: file.content,
        revision,
        modifiedAt: file.modifiedAt,
      });
      this.syncState.upsert({
        documentId,
        path: file.path,
        contentHash,
        revision,
      });
    }

    const job = await this.rag.reindex(vaultId, documents, signal);
    this.activeJobId = job.jobId;
    return {
      kind: "started",
      job,
      reindexRequired: status?.reindexRequired ?? false,
      reindexReason: status?.reindexReason ?? null,
    };
  }

  async watch(onUpdate?: (job: JobInfo) => void, signal?: AbortSignal): Promise<JobInfo> {
    if (!this.activeJobId) {
      throw new Error("No active reindex job");
    }
    const job = await this.jobs.watch(this.activeJobId, onUpdate, signal);
    if (job.status !== "pending" && job.status !== "running") {
      this.activeJobId = null;
    }
    return job;
  }

  async cancel(signal?: AbortSignal): Promise<JobInfo | null> {
    if (!this.activeJobId) {
      return null;
    }
    const jobId = this.activeJobId;
    await this.rag.cancelJob(jobId, signal);
    const job = await this.rag.getJob(jobId, signal);
    this.activeJobId = null;
    return job;
  }

  private async safeStatus(vaultId: VaultId, signal?: AbortSignal) {
    try {
      return await this.rag.status(vaultId, signal);
    } catch {
      return null;
    }
  }
}
