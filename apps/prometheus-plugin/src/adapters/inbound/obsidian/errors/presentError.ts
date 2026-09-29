import {
  isPrometheusPluginError,
  RuntimeApiError,
  type PrometheusPluginErrorCode,
  type RuntimeRecoveryAction,
} from "../../../../domain/errors";
import {
  ERROR_CATALOG,
  formatPresentedMessage,
  UNKNOWN_ERROR_ENTRY,
  type ErrorCatalogEntry,
} from "./errorCatalog";
import { sanitizeUserMessage } from "./sanitizeUserMessage";

export type PresentedError = {
  readonly code: PrometheusPluginErrorCode | "UNKNOWN";
  readonly message: string;
  readonly action: RuntimeRecoveryAction;
  readonly requestId: string | null;
};

/**
 * Map any thrown value to safe UI copy (cause + next step). Never uses raw
 * error.message for unknown errors, and never returns stack traces or absolute paths.
 */
export function presentError(error: unknown): PresentedError {
  if (error instanceof RuntimeApiError) {
    const entry = resolveEntry(error.code, error.recommendedAction);
    return {
      code: error.code,
      message: sanitizeUserMessage(formatPresentedMessage(entry)),
      action: entry.action,
      requestId: error.requestId,
    };
  }

  if (isPrometheusPluginError(error)) {
    const recommended =
      "recommendedAction" in error && typeof error.recommendedAction === "string"
        ? (error.recommendedAction as RuntimeRecoveryAction)
        : undefined;
    const entry = resolveEntry(error.code, recommended);
    return {
      code: error.code,
      message: sanitizeUserMessage(formatPresentedMessage(entry)),
      action: entry.action,
      requestId: null,
    };
  }

  return {
    code: "UNKNOWN",
    message: sanitizeUserMessage(formatPresentedMessage(UNKNOWN_ERROR_ENTRY)),
    action: UNKNOWN_ERROR_ENTRY.action,
    requestId: null,
  };
}

function resolveEntry(
  code: PrometheusPluginErrorCode,
  preferredAction?: RuntimeRecoveryAction,
): ErrorCatalogEntry {
  const base = ERROR_CATALOG[code] ?? UNKNOWN_ERROR_ENTRY;
  if (!preferredAction || preferredAction === base.action) {
    return base;
  }
  return { ...base, action: preferredAction, nextStep: nextStepForAction(preferredAction, base) };
}

function nextStepForAction(action: RuntimeRecoveryAction, base: ErrorCatalogEntry): string {
  switch (action) {
    case "retry":
      return "Retry the action.";
    case "reinitialize_runtime":
      return "Restart the runtime from the status panel.";
    case "restart_runtime":
      return "Restart the runtime from the status panel.";
    case "reindex":
      return "Reindex the Vault from the status panel.";
    case "select_model":
      return "Choose an installed model in Settings or the status panel.";
    case "update_plugin":
      return "Update the Prometheus plugin.";
    case "update_runtime":
      return "Update the runtime from Settings or the status panel.";
    case "reduce_document":
      return "Split the note or exclude its folder in Settings.";
    case "open_diagnostics":
      return "Open Diagnostics for details.";
    case "none":
      return base.nextStep;
    default: {
      const _exhaustive: never = action;
      return _exhaustive;
    }
  }
}
