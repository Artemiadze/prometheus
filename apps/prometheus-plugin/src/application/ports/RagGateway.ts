import type { DocumentId } from "../../domain/value-objects/DocumentId";
import type { SearchScope } from "../../domain/value-objects/SearchScope";
import type { VaultId } from "../../domain/value-objects/VaultId";
import type {
  ChatAnswerDto,
  HealthInfo,
  JobInfo,
  LlmModelInfo,
  RuntimeServiceStatus,
  SearchHitDto,
  UpsertDocumentInput,
} from "../dto/rag";

/**
 * Outbound port to the Prometheus runtime HTTP API.
 * Domain/application types only — no fetch, Response, or URL strings.
 */
export interface RagGateway {
  health(signal?: AbortSignal): Promise<HealthInfo>;
  status(signal?: AbortSignal): Promise<RuntimeServiceStatus>;
  listModels(signal?: AbortSignal): Promise<readonly LlmModelInfo[]>;
  upsertDocument(
    vaultId: VaultId,
    documentId: DocumentId,
    input: UpsertDocumentInput,
    signal?: AbortSignal,
  ): Promise<void>;
  deleteDocument(vaultId: VaultId, documentId: DocumentId, signal?: AbortSignal): Promise<void>;
  syncComplete(vaultId: VaultId, signal?: AbortSignal): Promise<void>;
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
    documents: readonly UpsertDocumentInput[],
    signal?: AbortSignal,
  ): Promise<JobInfo>;
  getJob(jobId: string, signal?: AbortSignal): Promise<JobInfo>;
  cancelJob(jobId: string, signal?: AbortSignal): Promise<void>;
}
