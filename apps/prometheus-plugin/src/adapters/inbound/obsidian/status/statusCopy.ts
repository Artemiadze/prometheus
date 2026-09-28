import type {
  ManagedRuntimeState,
  OllamaState,
  SelectedModel,
  RuntimeRecommendedAction,
} from "../../../../domain/entities/RuntimeStatus";
import type { RuntimeServiceStatus } from "../../../../application/dto/rag";
import type { SystemStatus } from "../../../../application/dto/system";
import type {
  IndexRecommendedAction,
  IndexStatus as IndexStatusUnion,
} from "../../../../domain/entities/IndexStatus";

export type StatusRow = {
  readonly id: string;
  readonly label: string;
  readonly value: string;
  readonly tone: "ok" | "warn" | "error" | "muted";
};

export function formatRuntimeValue(state: ManagedRuntimeState): {
  value: string;
  tone: StatusRow["tone"];
} {
  switch (state.kind) {
    case "missing":
      return { value: "Missing — Download required", tone: "error" };
    case "downloading":
      return { value: `Downloading… ${state.progressPercent}%`, tone: "warn" };
    case "verifying":
      return { value: "Verifying…", tone: "warn" };
    case "incompatible":
      return {
        value: `Incompatible (installed ${state.installedVersion}, required ${state.requiredRange})`,
        tone: "error",
      };
    case "starting":
      return { value: "Starting…", tone: "warn" };
    case "running":
      return { value: `Installed (v${state.version})`, tone: "ok" };
    case "stopped":
      return { value: "Stopped", tone: "error" };
    default: {
      const _exhaustive: never = state;
      return _exhaustive;
    }
  }
}

export function formatServiceValue(
  service: RuntimeServiceStatus | null,
  runtime: ManagedRuntimeState,
): { value: string; tone: StatusRow["tone"] } {
  if (runtime.kind === "running" && service) {
    return { value: "Running", tone: "ok" };
  }
  if (runtime.kind === "starting") {
    return { value: "Starting…", tone: "warn" };
  }
  if (runtime.kind === "running") {
    return { value: "Unavailable", tone: "warn" };
  }
  return { value: "Stopped", tone: "muted" };
}

export function formatIndexValue(index: IndexStatusUnion): {
  value: string;
  tone: StatusRow["tone"];
} {
  switch (index.kind) {
    case "notIndexed":
      return { value: "Not indexed", tone: "warn" };
    case "indexing":
      return { value: `Indexing… ${index.progressPercent}%`, tone: "warn" };
    case "ready":
      return { value: "Ready", tone: "ok" };
    case "reindexRequired":
      return { value: `Rebuild required — ${index.reason}`, tone: "warn" };
    case "corrupted":
      return { value: `Corrupted — ${index.reason}`, tone: "error" };
    default: {
      const _exhaustive: never = index;
      return _exhaustive;
    }
  }
}

export function formatOllamaValue(ollama: OllamaState): { value: string; tone: StatusRow["tone"] } {
  switch (ollama.kind) {
    case "notInstalled":
      return { value: "Not installed", tone: "error" };
    case "stopped":
      return { value: "Stopped", tone: "error" };
    case "running":
      return { value: "Running", tone: "ok" };
    default: {
      const _exhaustive: never = ollama;
      return _exhaustive;
    }
  }
}

export function formatModelValue(model: SelectedModel | null): {
  value: string;
  tone: StatusRow["tone"];
} {
  if (!model) {
    return { value: "Not selected", tone: "warn" };
  }
  if (!model.installed) {
    return { value: `${model.name} (not installed)`, tone: "error" };
  }
  return { value: `${model.name} (local)`, tone: "ok" };
}

export function formatDocumentCount(index: IndexStatusUnion): string {
  if (index.kind === "ready") {
    return index.documentCount.toLocaleString();
  }
  return "—";
}

export function formatChunkCount(index: IndexStatusUnion): string {
  if (index.kind === "ready") {
    return index.chunkCount.toLocaleString();
  }
  return "—";
}

export function formatLastIndexed(index: IndexStatusUnion, now: Date): string {
  if (index.kind !== "ready" || !index.lastIndexedAt) {
    return "—";
  }
  return formatRelativeTime(index.lastIndexedAt, now);
}

export function formatRelativeTime(at: Date, now: Date): string {
  const deltaMs = Math.max(0, now.getTime() - at.getTime());
  const seconds = Math.floor(deltaMs / 1000);
  if (seconds < 60) {
    return "just now";
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return minutes === 1 ? "1 minute ago" : `${minutes} minutes ago`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return hours === 1 ? "1 hour ago" : `${hours} hours ago`;
  }
  const days = Math.floor(hours / 24);
  return days === 1 ? "1 day ago" : `${days} days ago`;
}

export function buildStatusRows(
  status: SystemStatus,
  now: Date = status.fetchedAt,
): readonly StatusRow[] {
  const runtime = formatRuntimeValue(status.runtime.runtime);
  const service = formatServiceValue(status.service, status.runtime.runtime);
  const index = formatIndexValue(status.index);
  const ollama = formatOllamaValue(status.runtime.ollama);
  const model = formatModelValue(status.runtime.selectedModel);

  return [
    { id: "runtime", label: "Prometheus runtime", value: runtime.value, tone: runtime.tone },
    { id: "service", label: "Prometheus service", value: service.value, tone: service.tone },
    { id: "index", label: "Vector index", value: index.value, tone: index.tone },
    { id: "ollama", label: "Ollama", value: ollama.value, tone: ollama.tone },
    { id: "llm", label: "LLM", value: model.value, tone: model.tone },
    {
      id: "documents",
      label: "Documents",
      value: formatDocumentCount(status.index),
      tone: "muted",
    },
    {
      id: "chunks",
      label: "Chunks",
      value: formatChunkCount(status.index),
      tone: "muted",
    },
    {
      id: "lastIndexed",
      label: "Last indexed",
      value: formatLastIndexed(status.index, now),
      tone: "muted",
    },
  ];
}

export function runtimeActionLabel(action: RuntimeRecommendedAction): string | null {
  switch (action) {
    case "download":
      return "Download runtime";
    case "updateRuntime":
      return "Update runtime";
    case "restart":
      return "Restart runtime";
    case "wait":
    case "none":
      return null;
    default: {
      const _exhaustive: never = action;
      return _exhaustive;
    }
  }
}

export function indexActionLabel(action: IndexRecommendedAction): string | null {
  switch (action) {
    case "reindex":
      return "Reindex vault";
    case "wait":
    case "none":
      return null;
    default: {
      const _exhaustive: never = action;
      return _exhaustive;
    }
  }
}
