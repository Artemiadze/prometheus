import type {
  ChatAnswerDto,
  HealthInfo,
  JobInfo,
  LlmModelInfo,
  RuntimeServiceStatus,
  SearchHitDto,
  UpsertDocumentInput,
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
  searchResults: SearchHitDto[] = [];
  chatAnswer: ChatAnswerDto = {
    answer: "stub",
    sources: [],
    insufficientContext: false,
  };
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

  async health(signal?: AbortSignal): Promise<HealthInfo> {
    throwIfAborted(signal);
    return { status: "ok", version: "0.1.0" };
  }

  async status(signal?: AbortSignal): Promise<RuntimeServiceStatus> {
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
  ): Promise<void> {
    throwIfAborted(signal);
    const vaultDocs = this.ensureVault(vaultId);
    vaultDocs.set(documentId.value, { ...input, documentId: documentId.value });
    this.serviceStatus = {
      ...this.serviceStatus,
      documentCount: vaultDocs.size,
    };
  }

  async deleteDocument(
    vaultId: VaultId,
    documentId: DocumentId,
    signal?: AbortSignal,
  ): Promise<void> {
    throwIfAborted(signal);
    const vaultDocs = this.ensureVault(vaultId);
    vaultDocs.delete(documentId.value);
    this.serviceStatus = {
      ...this.serviceStatus,
      documentCount: vaultDocs.size,
    };
  }

  async syncComplete(vaultId: VaultId, signal?: AbortSignal): Promise<void> {
    throwIfAborted(signal);
    this.ensureVault(vaultId);
  }

  async search(
    _vaultId: VaultId,
    _query: string,
    _scope: SearchScope,
    limit: number,
    signal?: AbortSignal,
  ): Promise<readonly SearchHitDto[]> {
    throwIfAborted(signal);
    return this.searchResults.slice(0, limit);
  }

  async chat(
    _vaultId: VaultId,
    _question: string,
    _scope: SearchScope,
    signal?: AbortSignal,
  ): Promise<ChatAnswerDto> {
    throwIfAborted(signal);
    return this.chatAnswer;
  }

  async reindex(
    vaultId: VaultId,
    documents: readonly UpsertDocumentInput[],
    signal?: AbortSignal,
  ): Promise<JobInfo> {
    throwIfAborted(signal);
    for (const doc of documents) {
      const id = `doc-${doc.path.value}`;
      this.ensureVault(vaultId).set(id, { ...doc, documentId: id });
    }
    this.jobCounter += 1;
    const job: JobInfo = {
      jobId: `job-${this.jobCounter}`,
      status: "queued",
      progress: 0,
      error: null,
    };
    this.jobs.set(job.jobId, job);
    return job;
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
      this.jobs.set(jobId, { ...job, status: "cancelled" });
    }
  }

  /** Helper for tests that need a search hit without wiring adapters. */
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
