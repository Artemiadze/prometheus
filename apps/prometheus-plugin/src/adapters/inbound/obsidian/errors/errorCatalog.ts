import type { PrometheusPluginErrorCode, RuntimeRecoveryAction } from "../../../../domain/errors";

export type ErrorCatalogEntry = {
  readonly cause: string;
  readonly nextStep: string;
  readonly action: RuntimeRecoveryAction;
};

/**
 * User-facing copy for every plugin error code (Project_analytics §47 / PLG-74).
 * Typed as Record over the union so a new code without copy fails typecheck.
 */
export const ERROR_CATALOG: Record<PrometheusPluginErrorCode, ErrorCatalogEntry> = {
  INVALID_IDENTIFIER: {
    cause: "An identifier used by Prometheus is invalid.",
    nextStep: "Try the action again. If it persists, open Diagnostics.",
    action: "open_diagnostics",
  },
  INVALID_PATH: {
    cause: "A note path is not safe relative to the Vault.",
    nextStep: "Open a note inside the Vault and try again.",
    action: "none",
  },
  INVALID_SEARCH_SCOPE: {
    cause: "Search scope parameters are invalid.",
    nextStep: "Reset the search scope to Entire vault and try again.",
    action: "none",
  },
  INVARIANT_VIOLATION: {
    cause: "Prometheus hit an unexpected internal state.",
    nextStep: "Open Diagnostics and restart the runtime.",
    action: "open_diagnostics",
  },
  RUNTIME_NOT_INSTALLED: {
    cause: "Prometheus runtime is not installed.",
    nextStep: "Install it from the status panel. No cloud API is used.",
    action: "update_runtime",
  },
  RUNTIME_CHECKSUM_MISMATCH: {
    cause: "The downloaded Prometheus runtime failed integrity checks.",
    nextStep: "Re-download the runtime from Settings or the status panel.",
    action: "update_runtime",
  },
  RUNTIME_DOWNLOAD_FAILED: {
    cause: "Prometheus runtime download failed.",
    nextStep: "Check network access in Settings → Privacy, then retry.",
    action: "retry",
  },
  RUNTIME_START_TIMEOUT: {
    cause: "Prometheus runtime did not become ready in time.",
    nextStep: "Open Diagnostics to inspect process output, then restart.",
    action: "open_diagnostics",
  },
  RUNTIME_START_FAILED: {
    cause: "Prometheus runtime failed to start.",
    nextStep: "Open Diagnostics to inspect process output, then restart.",
    action: "open_diagnostics",
  },
  RUNTIME_VERSION_INCOMPATIBLE: {
    cause: "This plugin version is incompatible with the Prometheus runtime.",
    nextStep: "Update the runtime from Settings, or update the plugin.",
    action: "update_runtime",
  },
  RUNTIME_UNAVAILABLE: {
    cause: "Prometheus runtime is unavailable.",
    nextStep: "Start or restart it from the status panel.",
    action: "restart_runtime",
  },
  RUNTIME_REQUEST_TIMEOUT: {
    cause: "A request to the Prometheus runtime timed out.",
    nextStep: "Retry the action. If it keeps failing, restart the runtime.",
    action: "retry",
  },
  RUNTIME_SESSION_REQUIRED: {
    cause: "Prometheus runtime session must be initialized.",
    nextStep: "Restart the runtime from the status panel.",
    action: "reinitialize_runtime",
  },
  RUNTIME_CONTRACT_ERROR: {
    cause: "Prometheus runtime returned an invalid response.",
    nextStep: "Open Diagnostics and restart the runtime.",
    action: "open_diagnostics",
  },
  RUNTIME_API_ERROR: {
    cause: "Prometheus runtime request failed.",
    nextStep: "Open Diagnostics for details, then retry.",
    action: "open_diagnostics",
  },
  UNAUTHORIZED: {
    cause: "Prometheus runtime session is no longer valid.",
    nextStep: "Restart the runtime to create a new session.",
    action: "reinitialize_runtime",
  },
  JOB_NOT_FOUND: {
    cause: "A background indexing job was not found.",
    nextStep: "Retry indexing from the status panel.",
    action: "retry",
  },
  REVISION_CONFLICT: {
    cause: "The note revision conflicts with the indexed revision.",
    nextStep: "Retry sync; the note will be re-indexed.",
    action: "retry",
  },
  VAULT_NOT_INDEXED: {
    cause: "Vault has not been indexed.",
    nextStep: "Run indexing from the status panel.",
    action: "reindex",
  },
  INDEX_CORRUPTED: {
    cause: "The Vault index is corrupted.",
    nextStep: "Rebuild the index from the status panel.",
    action: "reindex",
  },
  INDEX_REBUILD_REQUIRED: {
    cause: "The Vault index must be rebuilt.",
    nextStep: "Reindex the Vault from the status panel.",
    action: "reindex",
  },
  DOCUMENT_TOO_LARGE: {
    cause: "The note is too large to index.",
    nextStep: "Split the note or exclude its folder in Settings.",
    action: "reduce_document",
  },
  VALIDATION_ERROR: {
    cause: "The runtime rejected an invalid request.",
    nextStep: "Open Diagnostics for details.",
    action: "open_diagnostics",
  },
  OLLAMA_UNAVAILABLE: {
    cause: "The local Ollama service is unavailable.",
    nextStep: "Start Ollama locally, then restart the Prometheus runtime.",
    action: "restart_runtime",
  },
  LLM_MODEL_NOT_FOUND: {
    cause: "The selected local model is not installed.",
    nextStep: "Choose an installed model in Settings or the status panel.",
    action: "select_model",
  },
  LLM_TIMEOUT: {
    cause: "Local model generation timed out.",
    nextStep: "Retry with a shorter question, or pick a smaller model.",
    action: "retry",
  },
  INTERNAL_ERROR: {
    cause: "Prometheus runtime encountered an internal error.",
    nextStep: "Open Diagnostics and restart the runtime.",
    action: "open_diagnostics",
  },
  QUERY_TOO_SHORT: {
    cause: "Search query is too short.",
    nextStep: "Type at least 3 characters.",
    action: "none",
  },
  NOTE_NOT_FOUND: {
    cause: "The note could not be found in the Vault.",
    nextStep: "It may have been moved or deleted. Pick another source.",
    action: "none",
  },
  NETWORK_ACCESS_DISABLED: {
    cause: "Runtime download is blocked because network access is disabled.",
    nextStep: "Enable it in Settings → Privacy, or switch back after installing.",
    action: "none",
  },
};

export const UNKNOWN_ERROR_ENTRY: ErrorCatalogEntry = {
  cause: "Something went wrong in Prometheus.",
  nextStep: "Open Diagnostics for details, then retry.",
  action: "open_diagnostics",
};

export function formatPresentedMessage(entry: ErrorCatalogEntry): string {
  return `${entry.cause} ${entry.nextStep}`;
}
