import { describe, expect, it } from "vitest";

import type { DiagnosticsSnapshot } from "../../../src/application/dto/diagnostics";
import {
  buildDiagnosticsReport,
  redactDiagnosticLine,
} from "../../../src/application/services/buildDiagnosticsReport";

function snapshot(overrides: Partial<DiagnosticsSnapshot> = {}): DiagnosticsSnapshot {
  return {
    pluginVersion: "0.1.0",
    runtimeVersion: "1.2.0",
    os: { platform: "linux", arch: "x64", release: "6.8.0" },
    ports: { runtime: 8765, ollamaAddress: "127.0.0.1:11434" },
    components: {
      runtimeKind: "running",
      runtimeStopReason: null,
      ollamaKind: "running",
      selectedModel: "qwen3:4b",
      modelInstalled: true,
      indexKind: "ready",
      documentCount: 10,
      chunkCount: 100,
    },
    settingsSummary: {
      runtimeMode: "managed",
      networkAccess: "updates_only",
      llmModel: "qwen3:4b",
      verboseLogging: false,
    },
    processOutput: [
      "[stdout] Authorization: Bearer supersecrettokenvalue0123456789abcdef",
      "[spawn] prometheus-runtime --session-token leaked-session-token-abcdefghijklmnop",
      "[stderr] note body: This is my private diary entry about work.",
    ],
    recentEvents: [
      {
        at: new Date("2026-01-01T00:00:00.000Z"),
        level: "error",
        name: "RUNTIME_UNAVAILABLE",
        fields: { attempt: 1 },
      },
    ],
    collectedAt: new Date("2026-01-01T00:00:00.000Z"),
    ...overrides,
  };
}

describe("buildDiagnosticsReport", () => {
  it("includes versions, OS, and component state", () => {
    const report = buildDiagnosticsReport(snapshot());
    expect(report).toContain("Plugin: 0.1.0");
    expect(report).toContain("Runtime: 1.2.0");
    expect(report).toContain("linux");
    expect(report).toContain("x64");
    expect(report).toContain("Runtime: running");
    expect(report).toContain("Documents: 10");
    expect(report).toContain("RUNTIME_UNAVAILABLE");
  });

  it("redacts tokens and does not echo seeded note/query text as report fields", () => {
    const report = buildDiagnosticsReport(snapshot());
    expect(report).not.toContain("supersecrettokenvalue");
    expect(report).not.toContain("leaked-session-token");
    expect(report).toContain("Bearer ***");
    expect(report).toContain("--session-token");
    expect(report).toContain("***");
    expect(report).not.toMatch(/Bearer\s+supersecret/i);
  });
});

describe("redactDiagnosticLine", () => {
  it("masks bearer, session token, and home paths", () => {
    expect(redactDiagnosticLine("Authorization: Bearer abcdef")).toContain("Bearer ***");
    expect(redactDiagnosticLine("--session-token=abcdefghijklmnop")).toContain("***");
    expect(redactDiagnosticLine("path=/home/artyom/vault/x")).toContain("/[home]");
  });
});
