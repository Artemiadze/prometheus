import type { SyncVaultPhase } from "../../../../application/use-cases/SynchronizeVault";

export type IndexingProgressInput = {
  readonly phase: SyncVaultPhase | "job";
  readonly processed: number;
  readonly total: number;
  readonly jobProgress: number;
  readonly elapsedMs: number;
};

export type IndexingProgressEstimate = {
  readonly processedDocs: number;
  readonly totalDocs: number;
  readonly percent: number;
  readonly etaMs: number | null;
  readonly label: string;
};

/**
 * Pure progress estimator for initial vault indexing (PLG-64).
 * Upload phases use exact counts; reconciling approximates from job progress.
 */
export function estimateIndexingProgress(input: IndexingProgressInput): IndexingProgressEstimate {
  const totalDocs = Math.max(0, input.total);
  let processedDocs: number;
  let percent: number;

  if (input.phase === "scanning") {
    processedDocs = 0;
    percent = 0;
  } else if (input.phase === "uploading") {
    processedDocs = Math.min(input.processed, totalDocs);
    percent = totalDocs > 0 ? Math.round((processedDocs / totalDocs) * 100) : 0;
  } else if (input.phase === "reconciling" || input.phase === "job") {
    const progress = clamp01(input.jobProgress);
    processedDocs = totalDocs > 0 ? Math.round(progress * totalDocs) : 0;
    percent = Math.round(progress * 100);
  } else {
    processedDocs = totalDocs;
    percent = 100;
  }

  const etaMs = estimateEtaMs(input.elapsedMs, percent);
  return {
    processedDocs,
    totalDocs,
    percent,
    etaMs,
    label: formatProgressLabel(processedDocs, totalDocs, percent, etaMs, input.phase),
  };
}

export function formatProgressLabel(
  processedDocs: number,
  totalDocs: number,
  percent: number,
  etaMs: number | null,
  phase: SyncVaultPhase | "job",
): string {
  if (phase === "scanning") {
    return "Scanning vault…";
  }
  if (phase === "completed") {
    return `Indexed ${totalDocs.toLocaleString()} documents.`;
  }
  const counts =
    totalDocs > 0
      ? `${processedDocs.toLocaleString()} / ${totalDocs.toLocaleString()} documents (${percent}%)`
      : `${percent}%`;
  if (etaMs === null) {
    return counts;
  }
  return `${counts} — about ${formatDuration(etaMs)} remaining`;
}

function estimateEtaMs(elapsedMs: number, percent: number): number | null {
  if (percent <= 0 || percent >= 100 || elapsedMs <= 0) {
    return null;
  }
  return Math.round((elapsedMs * (100 - percent)) / percent);
}

function formatDuration(ms: number): string {
  const seconds = Math.max(1, Math.round(ms / 1000));
  if (seconds < 60) {
    return `${seconds}s`;
  }
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return `${minutes}m`;
  }
  const hours = Math.round(minutes / 60);
  return `${hours}h`;
}

function clamp01(value: number): number {
  if (value < 0) {
    return 0;
  }
  if (value > 1) {
    return 1;
  }
  return value;
}

export function renderIndexingProgress(
  container: HTMLElement,
  estimate: IndexingProgressEstimate,
): void {
  container.empty();
  container.addClass("prometheus-status-view__progress");
  const bar = container.createDiv({ cls: "prometheus-status-view__progress-bar" });
  const fill = bar.createDiv({ cls: "prometheus-status-view__progress-fill" });
  fill.style.width = `${estimate.percent}%`;
  container.createDiv({
    cls: "prometheus-status-view__progress-label",
    text: estimate.label,
  });
}
