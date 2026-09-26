/**
 * Stable, presentation-safe error types for the Prometheus plugin domain.
 * Codes that can also arrive via the runtime HTTP envelope reuse the runtime
 * strings exactly; plugin-only codes cover failures before any HTTP call.
 */

export type PrometheusPluginErrorCode =
  | "INVALID_IDENTIFIER"
  | "INVALID_PATH"
  | "INVALID_SEARCH_SCOPE"
  | "INVARIANT_VIOLATION"
  | "RUNTIME_NOT_INSTALLED"
  | "RUNTIME_CHECKSUM_MISMATCH"
  | "RUNTIME_VERSION_INCOMPATIBLE"
  | "RUNTIME_UNAVAILABLE"
  | "RUNTIME_REQUEST_TIMEOUT"
  | "RUNTIME_SESSION_REQUIRED"
  | "RUNTIME_CONTRACT_ERROR"
  | "RUNTIME_API_ERROR"
  | "UNAUTHORIZED"
  | "JOB_NOT_FOUND"
  | "REVISION_CONFLICT"
  | "VAULT_NOT_INDEXED"
  | "INDEX_CORRUPTED"
  | "INDEX_REBUILD_REQUIRED"
  | "DOCUMENT_TOO_LARGE"
  | "VALIDATION_ERROR"
  | "OLLAMA_UNAVAILABLE"
  | "LLM_MODEL_NOT_FOUND"
  | "LLM_TIMEOUT"
  | "INTERNAL_ERROR"
  | "QUERY_TOO_SHORT"
  | "NOTE_NOT_FOUND";

export type RuntimeRecoveryAction =
  | "retry"
  | "reinitialize_runtime"
  | "restart_runtime"
  | "reindex"
  | "select_model"
  | "update_plugin"
  | "update_runtime"
  | "reduce_document"
  | "open_diagnostics"
  | "none";

export abstract class PrometheusPluginError extends Error {
  abstract readonly code: PrometheusPluginErrorCode;

  protected constructor(message: string) {
    super(message);
    this.name = new.target.name;
  }
}

export class InvalidIdentifierError extends PrometheusPluginError {
  readonly code = "INVALID_IDENTIFIER" as const;

  constructor() {
    super("Identifier format is invalid");
  }
}

export class InvalidPathError extends PrometheusPluginError {
  readonly code = "INVALID_PATH" as const;

  constructor() {
    super("Path must be safe and relative to the Vault");
  }
}

export class InvalidSearchScopeError extends PrometheusPluginError {
  readonly code = "INVALID_SEARCH_SCOPE" as const;

  constructor() {
    super("Search scope parameters are invalid");
  }
}

export class InvariantViolationError extends PrometheusPluginError {
  readonly code = "INVARIANT_VIOLATION" as const;

  constructor() {
    super("Domain invariant violated");
  }
}

export class RuntimeNotInstalledError extends PrometheusPluginError {
  readonly code = "RUNTIME_NOT_INSTALLED" as const;

  constructor() {
    super("Prometheus runtime is not installed");
  }
}

export class RuntimeChecksumMismatchError extends PrometheusPluginError {
  readonly code = "RUNTIME_CHECKSUM_MISMATCH" as const;

  constructor() {
    super("Prometheus runtime checksum mismatch");
  }
}

export class RuntimeVersionIncompatibleError extends PrometheusPluginError {
  readonly code = "RUNTIME_VERSION_INCOMPATIBLE" as const;
  readonly installedVersion: string;
  readonly requiredRange: string;
  readonly recommendedAction = "update_runtime" as const;

  constructor(installedVersion: string, requiredRange: string) {
    super(
      `Prometheus runtime version incompatible (installed ${installedVersion}, required ${requiredRange})`,
    );
    this.installedVersion = installedVersion;
    this.requiredRange = requiredRange;
  }
}

export class RuntimeUnavailableError extends PrometheusPluginError {
  readonly code = "RUNTIME_UNAVAILABLE" as const;

  constructor() {
    super("Prometheus runtime is unavailable");
  }
}

export class RuntimeRequestTimeoutError extends PrometheusPluginError {
  readonly code = "RUNTIME_REQUEST_TIMEOUT" as const;
  readonly timeoutMs: number;
  readonly recommendedAction = "retry" as const;

  constructor(timeoutMs: number) {
    super(`Prometheus runtime request timed out after ${timeoutMs} ms`);
    this.timeoutMs = timeoutMs;
  }
}

export class RuntimeSessionRequiredError extends PrometheusPluginError {
  readonly code = "RUNTIME_SESSION_REQUIRED" as const;
  readonly recommendedAction = "reinitialize_runtime" as const;

  constructor() {
    super("Prometheus runtime session must be initialized");
  }
}

export class RuntimeContractError extends PrometheusPluginError {
  readonly code = "RUNTIME_CONTRACT_ERROR" as const;
  readonly requestId: string | null;
  readonly recommendedAction = "open_diagnostics" as const;

  constructor(requestId: string | null = null) {
    super("Prometheus runtime returned an invalid response");
    this.requestId = requestId;
  }
}

export type RuntimeApiErrorDetails = {
  readonly code: PrometheusPluginErrorCode;
  readonly runtimeCode: string;
  readonly message: string;
  readonly requestId: string | null;
  readonly httpStatus: number;
  readonly recommendedAction: RuntimeRecoveryAction;
};

/**
 * Safe projection of the runtime error envelope.
 * The adapter supplies a client-owned message, never raw request data or headers.
 */
export class RuntimeApiError extends PrometheusPluginError {
  readonly code: PrometheusPluginErrorCode;
  readonly runtimeCode: string;
  readonly requestId: string | null;
  readonly httpStatus: number;
  readonly recommendedAction: RuntimeRecoveryAction;

  constructor(details: RuntimeApiErrorDetails) {
    super(details.message);
    this.code = details.code;
    this.runtimeCode = details.runtimeCode;
    this.requestId = details.requestId;
    this.httpStatus = details.httpStatus;
    this.recommendedAction = details.recommendedAction;
  }
}

export class VaultNotIndexedError extends PrometheusPluginError {
  readonly code = "VAULT_NOT_INDEXED" as const;

  constructor() {
    super("Vault has not been indexed");
  }
}

export class LlmModelNotFoundError extends PrometheusPluginError {
  readonly code = "LLM_MODEL_NOT_FOUND" as const;
  readonly modelName: string;

  constructor(modelName: string) {
    super(`Selected local model is not installed (${modelName})`);
    this.modelName = modelName;
  }
}

export class QueryTooShortError extends PrometheusPluginError {
  readonly code = "QUERY_TOO_SHORT" as const;

  constructor() {
    super("Search query is too short");
  }
}

export class NoteNotFoundError extends PrometheusPluginError {
  readonly code = "NOTE_NOT_FOUND" as const;
  readonly path: string;

  constructor(path: string) {
    super(`Note not found: ${path}`);
    this.path = path;
  }
}

export function isPrometheusPluginError(value: unknown): value is PrometheusPluginError {
  return value instanceof PrometheusPluginError;
}

export function isAbortError(error: unknown): boolean {
  return (
    (error instanceof DOMException && error.name === "AbortError") ||
    (error instanceof Error && error.name === "AbortError")
  );
}
