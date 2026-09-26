import type { JobStatus } from "../../../application/dto/rag";
import { RuntimeContractError } from "../../../domain/errors";

export type HealthResponse = {
  readonly status: string;
  readonly version: string;
};

export type StatusResponse = {
  readonly runtime_version: string;
  readonly api_version: string;
  readonly index_state: string;
  readonly llm_available: boolean;
  readonly llm_model: string;
  readonly document_count: number;
  readonly chunk_count: number;
  readonly last_indexed_at: string | null;
  readonly index_size_bytes: number;
  readonly reindex_required: boolean;
  readonly reindex_reason: string | null;
};

export type ModelResponse = {
  readonly name: string;
  readonly size_bytes: number;
  readonly quantization: string | null;
};

export type IndexDocumentResponse = {
  readonly document_id: string;
  readonly skipped: boolean;
  readonly relocated: boolean;
  readonly created_chunks: number;
  readonly deleted_chunks: number;
};

export type RemoveDocumentResponse = {
  readonly document_id: string;
  readonly removed: boolean;
  readonly removed_chunks: number;
};

export type JobStartedResponse = {
  readonly job_id: string;
  readonly status_url: string;
};

export type JobResponse = {
  readonly job_id: string;
  readonly status: JobStatus;
  readonly progress: number;
  readonly error: string | null;
};

export type SearchResultResponse = {
  readonly path: string;
  readonly heading: string | null;
  readonly text: string;
  readonly score: number;
};

export type ChatResponse = {
  readonly answer: string;
  readonly sources: readonly {
    readonly path: string;
    readonly heading: string | null;
  }[];
  readonly insufficient_context: boolean;
};

export function decodeHealth(payload: unknown, requestId: string | null): HealthResponse {
  const record = requiredRecord(payload, requestId);
  return {
    status: requiredString(record, "status", requestId),
    version: requiredString(record, "version", requestId),
  };
}

export function decodeStatus(payload: unknown, requestId: string | null): StatusResponse {
  const record = requiredRecord(payload, requestId);
  return {
    runtime_version: requiredString(record, "runtime_version", requestId),
    api_version: requiredString(record, "api_version", requestId),
    index_state: requiredString(record, "index_state", requestId),
    llm_available: requiredBoolean(record, "llm_available", requestId),
    llm_model: requiredString(record, "llm_model", requestId),
    document_count: requiredInteger(record, "document_count", requestId),
    chunk_count: requiredInteger(record, "chunk_count", requestId),
    last_indexed_at: nullableString(record, "last_indexed_at", requestId),
    index_size_bytes: requiredInteger(record, "index_size_bytes", requestId),
    reindex_required: requiredBoolean(record, "reindex_required", requestId),
    reindex_reason: nullableString(record, "reindex_reason", requestId),
  };
}

export function decodeModels(payload: unknown, requestId: string | null): readonly ModelResponse[] {
  const record = requiredRecord(payload, requestId);
  const models = requiredArray(record, "models", requestId);
  return models.map((value) => {
    const model = requiredRecord(value, requestId);
    return {
      name: requiredString(model, "name", requestId),
      size_bytes: requiredInteger(model, "size_bytes", requestId),
      quantization: nullableString(model, "quantization", requestId),
    };
  });
}

export function decodeIndexDocument(
  payload: unknown,
  requestId: string | null,
): IndexDocumentResponse {
  const record = requiredRecord(payload, requestId);
  return {
    document_id: requiredString(record, "document_id", requestId),
    skipped: requiredBoolean(record, "skipped", requestId),
    relocated: requiredBoolean(record, "relocated", requestId),
    created_chunks: requiredInteger(record, "created_chunks", requestId),
    deleted_chunks: requiredInteger(record, "deleted_chunks", requestId),
  };
}

export function decodeRemoveDocument(
  payload: unknown,
  requestId: string | null,
): RemoveDocumentResponse {
  const record = requiredRecord(payload, requestId);
  return {
    document_id: requiredString(record, "document_id", requestId),
    removed: requiredBoolean(record, "removed", requestId),
    removed_chunks: requiredInteger(record, "removed_chunks", requestId),
  };
}

export function decodeJobStarted(payload: unknown, requestId: string | null): JobStartedResponse {
  const record = requiredRecord(payload, requestId);
  return {
    job_id: requiredString(record, "job_id", requestId),
    status_url: requiredString(record, "status_url", requestId),
  };
}

export function decodeJob(payload: unknown, requestId: string | null): JobResponse {
  const record = requiredRecord(payload, requestId);
  const status = requiredString(record, "status", requestId);
  if (!isJobStatus(status)) {
    throw new RuntimeContractError(requestId);
  }
  const progress = requiredNumber(record, "progress", requestId);
  if (progress < 0 || progress > 1) {
    throw new RuntimeContractError(requestId);
  }
  return {
    job_id: requiredString(record, "job_id", requestId),
    status,
    progress,
    error: nullableString(record, "error", requestId),
  };
}

export function decodeSearch(
  payload: unknown,
  requestId: string | null,
): readonly SearchResultResponse[] {
  const record = requiredRecord(payload, requestId);
  return requiredArray(record, "results", requestId).map((value) => {
    const result = requiredRecord(value, requestId);
    return {
      path: requiredString(result, "path", requestId),
      heading: nullableString(result, "heading", requestId),
      text: requiredString(result, "text", requestId),
      score: requiredNumber(result, "score", requestId),
    };
  });
}

export function decodeChat(payload: unknown, requestId: string | null): ChatResponse {
  const record = requiredRecord(payload, requestId);
  const sources = requiredArray(record, "sources", requestId).map((value) => {
    const source = requiredRecord(value, requestId);
    return {
      path: requiredString(source, "path", requestId),
      heading: nullableString(source, "heading", requestId),
    };
  });
  return {
    answer: requiredString(record, "answer", requestId),
    sources,
    insufficient_context: requiredBoolean(record, "insufficient_context", requestId),
  };
}

export function decodeVoid(_payload: unknown, _requestId: string | null): void {
  return undefined;
}

function requiredRecord(value: unknown, requestId: string | null): Record<string, unknown> {
  if (!isRecord(value)) {
    throw new RuntimeContractError(requestId);
  }
  return value;
}

function requiredString(
  record: Record<string, unknown>,
  key: string,
  requestId: string | null,
): string {
  const value = record[key];
  if (typeof value !== "string") {
    throw new RuntimeContractError(requestId);
  }
  return value;
}

function nullableString(
  record: Record<string, unknown>,
  key: string,
  requestId: string | null,
): string | null {
  const value = record[key];
  if (value !== null && typeof value !== "string") {
    throw new RuntimeContractError(requestId);
  }
  return value;
}

function requiredBoolean(
  record: Record<string, unknown>,
  key: string,
  requestId: string | null,
): boolean {
  const value = record[key];
  if (typeof value !== "boolean") {
    throw new RuntimeContractError(requestId);
  }
  return value;
}

function requiredNumber(
  record: Record<string, unknown>,
  key: string,
  requestId: string | null,
): number {
  const value = record[key];
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new RuntimeContractError(requestId);
  }
  return value;
}

function requiredInteger(
  record: Record<string, unknown>,
  key: string,
  requestId: string | null,
): number {
  const value = requiredNumber(record, key, requestId);
  if (!Number.isInteger(value)) {
    throw new RuntimeContractError(requestId);
  }
  return value;
}

function requiredArray(
  record: Record<string, unknown>,
  key: string,
  requestId: string | null,
): readonly unknown[] {
  const value = record[key];
  if (!Array.isArray(value)) {
    throw new RuntimeContractError(requestId);
  }
  return value;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isJobStatus(value: string): value is JobStatus {
  return ["pending", "running", "completed", "failed", "cancelled"].includes(value);
}
