import type { SystemStatus } from "../../../../application/dto/system";
import type { IndexRecommendedAction } from "../../../../domain/entities/IndexStatus";
import type { RuntimeRecommendedAction } from "../../../../domain/entities/RuntimeStatus";

export type StatusBarKind = "ready" | "indexing" | "error" | "busy";

export type StatusBarLabel = {
  readonly kind: StatusBarKind;
  readonly text: string;
};

/**
 * Compact status-bar label derived from SystemStatus (PLG-62).
 * Pure — no Obsidian or DOM imports.
 */
export function formatStatusBarLabel(
  status: SystemStatus | null,
  runtimeAction: RuntimeRecommendedAction,
  indexAction: IndexRecommendedAction,
): StatusBarLabel {
  if (!status) {
    return { kind: "busy", text: "Prometheus…" };
  }

  const runtime = status.runtime.runtime;
  if (
    runtime.kind === "downloading" ||
    runtime.kind === "verifying" ||
    runtime.kind === "starting"
  ) {
    return { kind: "busy", text: "Prometheus…" };
  }

  if (
    runtimeAction === "download" ||
    runtimeAction === "updateRuntime" ||
    runtimeAction === "restart" ||
    indexAction === "reindex" ||
    status.index.kind === "corrupted" ||
    status.runtime.ollama.kind !== "running" ||
    (status.runtime.selectedModel !== null && !status.runtime.selectedModel.installed)
  ) {
    if (status.index.kind === "indexing") {
      return {
        kind: "indexing",
        text: `Prometheus: Indexing ${status.index.progressPercent}%`,
      };
    }
    return { kind: "error", text: "Prometheus: Error" };
  }

  if (status.index.kind === "indexing") {
    return {
      kind: "indexing",
      text: `Prometheus: Indexing ${status.index.progressPercent}%`,
    };
  }

  if (status.index.kind === "ready" && runtime.kind === "running") {
    return { kind: "ready", text: "Prometheus: Ready" };
  }

  return { kind: "busy", text: "Prometheus…" };
}
