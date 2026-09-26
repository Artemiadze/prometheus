import {
  RuntimeApiError,
  type PrometheusPluginErrorCode,
  type RuntimeRecoveryAction,
} from "../../../domain/errors";

type ErrorDescriptor = {
  readonly code: PrometheusPluginErrorCode;
  readonly message: string;
  readonly action: RuntimeRecoveryAction;
};

const ERROR_DESCRIPTORS: Readonly<Record<string, ErrorDescriptor>> = {
  UNAUTHORIZED: {
    code: "UNAUTHORIZED",
    message: "Prometheus runtime session is no longer valid",
    action: "reinitialize_runtime",
  },
  JOB_NOT_FOUND: {
    code: "JOB_NOT_FOUND",
    message: "Prometheus background job was not found",
    action: "retry",
  },
  REVISION_CONFLICT: {
    code: "REVISION_CONFLICT",
    message: "The note revision conflicts with the indexed revision",
    action: "retry",
  },
  VAULT_NOT_INDEXED: {
    code: "VAULT_NOT_INDEXED",
    message: "Vault has not been indexed",
    action: "reindex",
  },
  INDEX_CORRUPTED: {
    code: "INDEX_CORRUPTED",
    message: "The Vault index is corrupted",
    action: "reindex",
  },
  INDEX_REBUILD_REQUIRED: {
    code: "INDEX_REBUILD_REQUIRED",
    message: "The Vault index must be rebuilt",
    action: "reindex",
  },
  RUNTIME_VERSION_INCOMPATIBLE: {
    code: "RUNTIME_VERSION_INCOMPATIBLE",
    message: "This plugin version is incompatible with the Prometheus runtime",
    action: "update_plugin",
  },
  DOCUMENT_TOO_LARGE: {
    code: "DOCUMENT_TOO_LARGE",
    message: "The note is too large to index",
    action: "reduce_document",
  },
  QUERY_TOO_SHORT: {
    code: "QUERY_TOO_SHORT",
    message: "Search query is too short",
    action: "none",
  },
  VALIDATION_ERROR: {
    code: "VALIDATION_ERROR",
    message: "The runtime rejected an invalid request",
    action: "open_diagnostics",
  },
  OLLAMA_UNAVAILABLE: {
    code: "OLLAMA_UNAVAILABLE",
    message: "The local Ollama service is unavailable",
    action: "restart_runtime",
  },
  LLM_MODEL_NOT_FOUND: {
    code: "LLM_MODEL_NOT_FOUND",
    message: "The selected local model is not installed",
    action: "select_model",
  },
  LLM_TIMEOUT: {
    code: "LLM_TIMEOUT",
    message: "Local model generation timed out",
    action: "retry",
  },
  INTERNAL_ERROR: {
    code: "INTERNAL_ERROR",
    message: "Prometheus runtime encountered an internal error",
    action: "open_diagnostics",
  },
};

export function mapRuntimeApiError(
  payload: unknown,
  httpStatus: number,
  responseRequestId: string | null,
): RuntimeApiError {
  const body = readErrorBody(payload);
  const runtimeCode = httpStatus === 401 ? "UNAUTHORIZED" : (body?.code ?? "UNKNOWN");
  const descriptor = ERROR_DESCRIPTORS[runtimeCode] ?? {
    code: "RUNTIME_API_ERROR" as const,
    message: "Prometheus runtime request failed",
    action: "open_diagnostics" as const,
  };
  return new RuntimeApiError({
    code: descriptor.code,
    runtimeCode,
    message: descriptor.message,
    requestId: body?.requestId ?? responseRequestId,
    httpStatus,
    recommendedAction: descriptor.action,
  });
}

function readErrorBody(
  payload: unknown,
): { readonly code: string; readonly requestId: string | null } | null {
  if (!isRecord(payload) || !isRecord(payload.error)) {
    return null;
  }
  const code = payload.error.code;
  const requestId = payload.error.request_id;
  if (typeof code !== "string") {
    return null;
  }
  return {
    code,
    requestId: typeof requestId === "string" ? requestId : null,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
