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
  | "VAULT_NOT_INDEXED"
  | "LLM_MODEL_NOT_FOUND"
  | "QUERY_TOO_SHORT"
  | "NOTE_NOT_FOUND";

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
