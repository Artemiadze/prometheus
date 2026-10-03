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
} from "../../../application/dto/rag";
import type { RagGateway } from "../../../application/ports/RagGateway";
import { assertRuntimeVersionCompatible } from "../../../application/services/RuntimeVersion";
import { SourceReference } from "../../../domain/entities/SourceReference";
import { RuntimeContractError } from "../../../domain/errors";
import type { DocumentId } from "../../../domain/value-objects/DocumentId";
import { NotePath } from "../../../domain/value-objects/NotePath";
import type { SearchScope } from "../../../domain/value-objects/SearchScope";
import type { VaultId } from "../../../domain/value-objects/VaultId";
import {
  decodeChat,
  decodeHealth,
  decodeIndexDocument,
  decodeJob,
  decodeJobStarted,
  decodeModels,
  decodeRemoveDocument,
  decodeSearch,
  decodeStatus,
  decodeVoid,
} from "./contracts";
import { CHAT_REQUEST_TIMEOUT_MS, type RuntimeHttpClient } from "./RuntimeHttpClient";

export class HttpRagGateway implements RagGateway {
  private compatibleConnectionKey: string | null = null;

  constructor(private readonly http: RuntimeHttpClient) {}

  async health(signal?: AbortSignal): Promise<HealthInfo> {
    const health = await this.http.request("/health", {
      protected: false,
      signal,
      decode: decodeHealth,
    });
    assertRuntimeVersionCompatible(health.version);
    this.compatibleConnectionKey = this.http.currentConnectionKey();
    return health;
  }

  async status(vaultId: VaultId, signal?: AbortSignal): Promise<RuntimeServiceStatus> {
    await this.ensureCompatible(signal);
    return this.http.request(`/status?vaultId=${encodeURIComponent(vaultId.value)}`, {
      signal,
      decode: (payload, requestId) => {
        const response = decodeStatus(payload, requestId);
        return {
          runtimeVersion: response.runtime_version,
          apiVersion: response.api_version,
          indexState: response.index_state,
          llmAvailable: response.llm_available,
          llmModel: response.llm_model,
          documentCount: response.document_count,
          chunkCount: response.chunk_count,
          lastIndexedAt: parseDate(response.last_indexed_at, requestId),
          indexSizeBytes: response.index_size_bytes,
          reindexRequired: response.reindex_required,
          reindexReason: response.reindex_reason,
        };
      },
    });
  }

  async listModels(signal?: AbortSignal): Promise<readonly LlmModelInfo[]> {
    await this.ensureCompatible(signal);
    return this.http.request("/models", {
      signal,
      decode: (payload, requestId) =>
        decodeModels(payload, requestId).map((model) => ({
          name: model.name,
          sizeBytes: model.size_bytes,
          quantization: model.quantization,
        })),
    });
  }

  async upsertDocument(
    vaultId: VaultId,
    documentId: DocumentId,
    input: UpsertDocumentInput,
    signal?: AbortSignal,
  ): Promise<UpsertDocumentResult> {
    await this.ensureCompatible(signal);
    return this.http.request(documentPath(vaultId, documentId), {
      method: "PUT",
      signal,
      body: serializeDocument(input),
      decode: (payload, requestId) => {
        const response = decodeIndexDocument(payload, requestId);
        return {
          documentId: response.document_id,
          skipped: response.skipped,
          relocated: response.relocated,
          createdChunks: response.created_chunks,
          deletedChunks: response.deleted_chunks,
        };
      },
    });
  }

  async deleteDocument(
    vaultId: VaultId,
    documentId: DocumentId,
    signal?: AbortSignal,
  ): Promise<void> {
    await this.ensureCompatible(signal);
    await this.http.request(documentPath(vaultId, documentId), {
      method: "DELETE",
      signal,
      decode: (payload, requestId) => {
        decodeRemoveDocument(payload, requestId);
      },
    });
  }

  async syncComplete(
    vaultId: VaultId,
    entries: readonly VaultSnapshotEntry[],
    signal?: AbortSignal,
  ): Promise<JobInfo> {
    await this.ensureCompatible(signal);
    return this.http.request(`/vaults/${encodeURIComponent(vaultId.value)}/sync/complete`, {
      method: "POST",
      signal,
      body: {
        entries: entries.map((entry) => ({
          document_id: entry.documentId.value,
          path: entry.path.value,
          content_hash: entry.contentHash,
          revision: entry.revision,
          modified_at: entry.modifiedAt.toISOString(),
        })),
      },
      decode: decodeStartedJob,
    });
  }

  async search(
    vaultId: VaultId,
    query: string,
    scope: SearchScope,
    limit: number,
    signal?: AbortSignal,
  ): Promise<readonly SearchHitDto[]> {
    await this.ensureCompatible(signal);
    return this.http.request(`/vaults/${encodeURIComponent(vaultId.value)}/search`, {
      method: "POST",
      signal,
      body: { query, limit, scope: scope.serialize() },
      decode: (payload, requestId) =>
        decodeSearch(payload, requestId).map((result) => {
          try {
            return {
              path: NotePath.create(result.path),
              heading: result.heading,
              text: result.text,
              score: result.score,
            };
          } catch {
            throw new RuntimeContractError(requestId);
          }
        }),
    });
  }

  async chat(
    vaultId: VaultId,
    question: string,
    scope: SearchScope,
    signal?: AbortSignal,
  ): Promise<ChatAnswerDto> {
    await this.ensureCompatible(signal);
    return this.http.request(`/vaults/${encodeURIComponent(vaultId.value)}/chat`, {
      method: "POST",
      signal,
      timeoutMs: CHAT_REQUEST_TIMEOUT_MS,
      body: { query: question, scope: scope.serialize() },
      decode: (payload, requestId) => {
        const response = decodeChat(payload, requestId);
        try {
          return {
            answer: response.answer,
            sources: response.sources.map((source) =>
              SourceReference.create(source.path, source.heading),
            ),
            insufficientContext: response.insufficient_context,
          };
        } catch {
          throw new RuntimeContractError(requestId);
        }
      },
    });
  }

  async reindex(
    vaultId: VaultId,
    documents: readonly ReindexDocumentInput[],
    signal?: AbortSignal,
  ): Promise<JobInfo> {
    await this.ensureCompatible(signal);
    return this.http.request(`/vaults/${encodeURIComponent(vaultId.value)}/reindex`, {
      method: "POST",
      signal,
      body: {
        documents: documents.map((document) => ({
          document_id: document.documentId.value,
          ...serializeDocument(document),
        })),
      },
      decode: decodeStartedJob,
    });
  }

  async getJob(jobId: string, signal?: AbortSignal): Promise<JobInfo> {
    await this.ensureCompatible(signal);
    return this.http.request(`/jobs/${encodeURIComponent(jobId)}`, {
      signal,
      decode: (payload, requestId) => {
        const response = decodeJob(payload, requestId);
        return {
          jobId: response.job_id,
          status: response.status,
          progress: response.progress,
          error: response.error,
        };
      },
    });
  }

  async cancelJob(jobId: string, signal?: AbortSignal): Promise<void> {
    await this.ensureCompatible(signal);
    await this.http.request(`/jobs/${encodeURIComponent(jobId)}`, {
      method: "DELETE",
      signal,
      decode: decodeVoid,
    });
  }

  private async ensureCompatible(signal?: AbortSignal): Promise<void> {
    const connectionKey = this.http.currentConnectionKey();
    if (connectionKey !== null && connectionKey === this.compatibleConnectionKey) {
      return;
    }
    await this.health(signal);
  }
}

function documentPath(vaultId: VaultId, documentId: DocumentId): string {
  return `/vaults/${encodeURIComponent(vaultId.value)}/documents/${encodeURIComponent(
    documentId.value,
  )}`;
}

function serializeDocument(input: UpsertDocumentInput): {
  readonly path: string;
  readonly content: string;
  readonly revision: number;
  readonly modified_at: string;
} {
  return {
    path: input.path.value,
    content: input.content,
    revision: input.revision,
    modified_at: input.modifiedAt.toISOString(),
  };
}

function decodeStartedJob(payload: unknown, requestId: string | null): JobInfo {
  const response = decodeJobStarted(payload, requestId);
  return {
    jobId: response.job_id,
    status: "pending",
    progress: 0,
    error: null,
  };
}

function parseDate(value: string | null, requestId: string | null): Date | null {
  if (value === null) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    throw new RuntimeContractError(requestId);
  }
  return date;
}
