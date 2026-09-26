import type { DocumentId } from "../../domain/value-objects/DocumentId";
import type { SearchScope } from "../../domain/value-objects/SearchScope";
import type { VaultId } from "../../domain/value-objects/VaultId";
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
} from "../dto/rag";

/**
 * Outbound port to the Prometheus runtime HTTP API.
 * Domain/application types only — no fetch, Response, or URL strings.
 */
export interface RagGateway {
  health(signal?: AbortSignal): Promise<HealthInfo>;
  status(vaultId: VaultId, signal?: AbortSignal): Promise<RuntimeServiceStatus>;
  listModels(signal?: AbortSignal): Promise<readonly LlmModelInfo[]>;
  upsertDocument(
    vaultId: VaultId,
    documentId: DocumentId,
    input: UpsertDocumentInput,
    signal?: AbortSignal,
  ): Promise<UpsertDocumentResult>;
  deleteDocument(vaultId: VaultId, documentId: DocumentId, signal?: AbortSignal): Promise<void>;
  syncComplete(
    vaultId: VaultId,
    entries: readonly VaultSnapshotEntry[],
    signal?: AbortSignal,
  ): Promise<JobInfo>;
  search(
    vaultId: VaultId,
    query: string,
    scope: SearchScope,
    limit: number,
    signal?: AbortSignal,
  ): Promise<readonly SearchHitDto[]>;
  chat(
    vaultId: VaultId,
    question: string,
    scope: SearchScope,
    signal?: AbortSignal,
  ): Promise<ChatAnswerDto>;
  reindex(
    vaultId: VaultId,
    documents: readonly ReindexDocumentInput[],
    signal?: AbortSignal,
  ): Promise<JobInfo>;
  getJob(jobId: string, signal?: AbortSignal): Promise<JobInfo>;
  cancelJob(jobId: string, signal?: AbortSignal): Promise<void>;
}
