import type { DiagnosticsSnapshot } from "../dto/diagnostics";

/**
 * Render a privacy-safe plain-text diagnostics report (PLG-75).
 */
export function buildDiagnosticsReport(snapshot: DiagnosticsSnapshot): string {
  const lines: string[] = [
    "Prometheus Diagnostics Report",
    `Collected at: ${snapshot.collectedAt.toISOString()}`,
    "",
    "== Versions ==",
    `Plugin: ${snapshot.pluginVersion}`,
    `Runtime: ${snapshot.runtimeVersion ?? "unknown"}`,
    "",
    "== Environment ==",
    `OS: ${snapshot.os.platform} ${snapshot.os.release} (${snapshot.os.arch})`,
    `Runtime port: ${snapshot.ports.runtime ?? "n/a"}`,
    `Ollama address: ${snapshot.ports.ollamaAddress}`,
    "",
    "== Components ==",
    `Runtime: ${snapshot.components.runtimeKind}${
      snapshot.components.runtimeStopReason
        ? ` (reason: ${snapshot.components.runtimeStopReason})`
        : ""
    }`,
    `Ollama: ${snapshot.components.ollamaKind}`,
    `Model: ${
      snapshot.components.selectedModel
        ? `${snapshot.components.selectedModel}${
            snapshot.components.modelInstalled === false ? " (not installed)" : ""
          }`
        : "none"
    }`,
    `Index: ${snapshot.components.indexKind}`,
    `Documents: ${snapshot.components.documentCount ?? "n/a"}`,
    `Chunks: ${snapshot.components.chunkCount ?? "n/a"}`,
    "",
    "== Settings ==",
    `Runtime mode: ${snapshot.settingsSummary.runtimeMode}`,
    `Network access: ${snapshot.settingsSummary.networkAccess}`,
    `LLM model: ${snapshot.settingsSummary.llmModel}`,
    `Verbose logging: ${snapshot.settingsSummary.verboseLogging ? "on" : "off"}`,
    "",
    "== Recent errors / events ==",
  ];

  if (snapshot.recentEvents.length === 0) {
    lines.push("(none)");
  } else {
    for (const event of snapshot.recentEvents) {
      const fieldParts = Object.entries(event.fields)
        .map(([key, value]) => `${key}=${String(value)}`)
        .join(" ");
      lines.push(
        `${event.at.toISOString()} [${event.level}] ${event.name}${
          fieldParts ? ` ${fieldParts}` : ""
        }`,
      );
    }
  }

  lines.push("", "== Runtime process output ==");
  if (snapshot.processOutput.length === 0) {
    lines.push("(none)");
  } else {
    for (const line of snapshot.processOutput) {
      lines.push(redactDiagnosticLine(line));
    }
  }

  lines.push("");
  return lines.join("\n");
}

/**
 * Mask tokens, bearer headers, and home-directory prefixes in process output.
 */
export function redactDiagnosticLine(line: string): string {
  return line
    .replace(/Bearer\s+\S+/gi, "Bearer ***")
    .replace(/--session-token=\S+/g, "--session-token=***")
    .replace(/--session-token\s+\S+/g, "--session-token ***")
    .replace(/\b[A-Za-z0-9_-]{32,}\b/g, "***")
    .replace(/\/(?:home|Users)\/[^\s/]+/g, "/[home]")
    .replace(/[A-Za-z]:\\Users\\[^\s\\]+/g, "C:\\Users\\[home]");
}
