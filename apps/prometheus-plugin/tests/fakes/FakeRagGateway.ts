import type {
  ChatAnswerDto,
  HealthInfo,
  JobInfo,
  LlmModelInfo,
  ReindexDocumentInput,
  RuntimeServiceStatus,
  SearchHitDto,
  UpsertDocumentInput,
  UpsertDocumentResult,
  VaultSnapshotEntry,
} from "../../src/application/dto/rag";
import type { RagGateway } from "../../src/application/ports/RagGateway";
import type { SourceReference } from "../../src/domain/entities/SourceReference";
import type { DocumentId } from "../../src/domain/value-objects/DocumentId";
import type { SearchScope } from "../../src/domain/value-objects/SearchScope";
import type { VaultId } from "../../src/domain/value-objects/VaultId";
import { NotePath } from "../../src/domain/value-objects/NotePath";

type StoredDoc = UpsertDocumentInput & { documentId: string };

export class FakeRagGateway implements RagGateway {
  private readonly documents = new Map<string, Map<string, StoredDoc>>();
  private readonly jobs = new Map<string, JobInfo>();
  private jobCounter = 0;
  private activeJobId: string | null = null;
  healthResult: HealthInfo | null = { status: "ok", version: "0.1.0" };
  healthFailCount = 0;
  searchResults: SearchHitDto[] = [];
  chatAnswer: ChatAnswerDto = {
    answer: "stub",
    sources: [],
    insufficientContext: false,
  };
  chatDelayMs = 0;
  searchCalls = 0;
  chatCalls = 0;
  upsertCalls = 0;
  deleteCalls = 0;
  reindexCalls = 0;
  syncCompleteCalls = 0;
  holdJobsPending = false;
  lastSyncEntries: readonly VaultSnapshotEntry[] = [];
  models: LlmModelInfo[] = [{ name: "qwen3:4b", sizeBytes: 1, quantization: "Q4" }];
  serviceStatus: RuntimeServiceStatus = {
    runtimeVersion: "0.1.0",
    apiVersion: "v1",
    indexState: "ready",
    llmAvailable: true,
    llmModel: "qwen3:4b",
    documentCount: 0,
    chunkCount: 0,
    lastIndexedAt: null,
    indexSizeBytes: 0,
    reindexRequired: false,
    reindexReason: null,
  };
  upsertShouldFailPaths = new Set<string>();

  async health(signal?: AbortSignal): Promise<HealthInfo> {
    throwIfAborted(signal);
    if (this.healthFailCount > 0) {
      this.healthFailCount -= 1;
      throw new Error("health unavailable");
    }
    if (this.healthResult === null) {
      throw new Error("health unavailable");
    }
    return this.healthResult;
  }

  async status(_vaultId: VaultId, signal?: AbortSignal): Promise<RuntimeServiceStatus> {
    throwIfAborted(signal);
    return this.serviceStatus;
  }

  async listModels(signal?: AbortSignal): Promise<readonly LlmModelInfo[]> {
    throwIfAborted(signal);
    return this.models;
  }

  async upsertDocument(
    vaultId: VaultId,
    documentId: DocumentId,
    input: UpsertDocumentInput,
    signal?: AbortSignal,
  ): Promise<UpsertDocumentResult> {
    throwIfAborted(signal);
    this.upsertCalls += 1;
    if (this.upsertShouldFailPaths.has(input.path.value)) {
      throw new Error(`upsert failed: ${input.path.value}`);
    }
    const vaultDocs = this.ensureVault(vaultId);
    const previous = vaultDocs.get(documentId.value);
    const relocated = previous !== undefined && previous.path.value !== input.path.value;
    const skipped = previous !== undefined && previous.content === input.content && !relocated;
    vaultDocs.set(documentId.value, { ...input, documentId: documentId.value });
    this.serviceStatus = {
      ...this.serviceStatus,
      documentCount: vaultDocs.size,
    };
    return {
      documentId: documentId.value,
      skipped,
      relocated,
      createdChunks: skipped ? 0 : 1,
      deletedChunks: 0,
    };
  }

  async deleteDocument(
    vaultId: VaultId,
    documentId: DocumentId,
    signal?: AbortSignal,
  ): Promise<void> {
    throwIfAborted(signal);
    this.deleteCalls += 1;
    const vaultDocs = this.ensureVault(vaultId);
    vaultDocs.delete(documentId.value);
    this.serviceStatus = {
      ...this.serviceStatus,
      documentCount: vaultDocs.size,
    };
  }

  async syncComplete(
    vaultId: VaultId,
    entries: readonly VaultSnapshotEntry[],
    signal?: AbortSignal,
  ): Promise<JobInfo> {
    throwIfAborted(signal);
    this.syncCompleteCalls += 1;
    this.lastSyncEntries = entries;
    this.ensureVault(vaultId);
    return this.createOrReuseJob();
  }

  async search(
    _vaultId: VaultId,
    _query: string,
    _scope: SearchScope,
    limit: number,
    signal?: AbortSignal,
  ): Promise<readonly SearchHitDto[]> {
    throwIfAborted(signal);
    this.searchCalls += 1;
    return this.searchResults.slice(0, limit);
  }

  async chat(
    _vaultId: VaultId,
    _question: string,
    _scope: SearchScope,
    signal?: AbortSignal,
  ): Promise<ChatAnswerDto> {
    throwIfAborted(signal);
    this.chatCalls += 1;
    if (this.chatDelayMs > 0) {
      await delay(this.chatDelayMs, signal);
    }
    throwIfAborted(signal);
    return this.chatAnswer;
  }

  async reindex(
    vaultId: VaultId,
    documents: readonly ReindexDocumentInput[],
    signal?: AbortSignal,
  ): Promise<JobInfo> {
    throwIfAborted(signal);
    if (this.activeJobId) {
      const active = this.jobs.get(this.activeJobId);
      if (active && (active.status === "pending" || active.status === "running")) {
        return active;
      }
    }
    this.reindexCalls += 1;
    for (const doc of documents) {
      this.ensureVault(vaultId).set(doc.documentId.value, {
        path: doc.path,
        content: doc.content,
        revision: doc.revision,
        modifiedAt: doc.modifiedAt,
        documentId: doc.documentId.value,
      });
    }
    return this.createOrReuseJob();
  }

  async getJob(jobId: string, signal?: AbortSignal): Promise<JobInfo> {
    throwIfAborted(signal);
    const job = this.jobs.get(jobId);
    if (!job) {
      throw new Error(`Job not found: ${jobId}`);
    }
    return job;
  }

  async cancelJob(jobId: string, signal?: AbortSignal): Promise<void> {
    throwIfAborted(signal);
    const job = this.jobs.get(jobId);
    if (job) {
      this.setJob({ ...job, status: "cancelled" });
    }
  }

  setJob(job: JobInfo): void {
    this.jobs.set(job.jobId, job);
    if (job.status === "pending" || job.status === "running") {
      this.activeJobId = job.jobId;
    } else if (this.activeJobId === job.jobId) {
      this.activeJobId = null;
    }
  }

  stubSearchHit(path: string, text: string, score = 1): void {
    this.searchResults.push({
      path: NotePath.create(path),
      heading: null,
      text,
      score,
    });
  }

  stubChat(answer: string, sources: SourceReference[] = [], insufficientContext = false): void {
    this.chatAnswer = { answer, sources, insufficientContext };
  }

  private createOrReuseJob(): JobInfo {
    if (this.activeJobId) {
      const active = this.jobs.get(this.activeJobId);
      if (active && (active.status === "pending" || active.status === "running")) {
        return active;
      }
    }
    this.jobCounter += 1;
    const job: JobInfo = {
      jobId: `job-${this.jobCounter}`,
      status: this.holdJobsPending ? "pending" : "completed",
      progress: this.holdJobsPending ? 0 : 1,
      error: null,
    };
    this.setJob(job);
    return job;
  }

  private ensureVault(vaultId: VaultId): Map<string, StoredDoc> {
    const key = vaultId.value;
    let vaultDocs = this.documents.get(key);
    if (!vaultDocs) {
      vaultDocs = new Map();
      this.documents.set(key, vaultDocs);
    }
    return vaultDocs;
  }
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw new DOMException("The operation was aborted", "AbortError");
  }
}

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    if (!signal) {
      return;
    }
    const onAbort = (): void => {
      clearTimeout(timer);
      reject(new DOMException("The operation was aborted", "AbortError"));
    };
    if (signal.aborted) {
      onAbort();
      return;
    }
    signal.addEventListener("abort", onAbort, { once: true });
  });
}
