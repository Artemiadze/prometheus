import { describe, expect, it } from "vitest";

import {
  buildStatusRows,
  formatRuntimeValue,
  indexActionLabel,
  runtimeActionLabel,
} from "../../../../../src/adapters/inbound/obsidian/status/statusCopy";
import { IndexStatus } from "../../../../../src/domain/entities/IndexStatus";
import {
  createRuntimeStatus,
  ManagedRuntimeState,
  OllamaState,
} from "../../../../../src/domain/entities/RuntimeStatus";
import type { SystemStatus } from "../../../../../src/application/dto/system";

function sampleStatus(overrides: Partial<SystemStatus> = {}): SystemStatus {
  return {
    runtime: createRuntimeStatus({
      runtime: ManagedRuntimeState.running("1.2.0"),
      ollama: OllamaState.running(),
      selectedModel: { name: "qwen3:4b", installed: true },
    }),
    index: IndexStatus.ready({
      documentCount: 4169,
      chunkCount: 27481,
      lastIndexedAt: new Date(0),
      indexSizeBytes: 1,
    }),
    service: {
      runtimeVersion: "1.2.0",
      apiVersion: "v1",
      indexState: "ready",
      llmAvailable: true,
      llmModel: "qwen3:4b",
      documentCount: 4169,
      chunkCount: 27481,
      lastIndexedAt: new Date(0),
      indexSizeBytes: 1,
      reindexRequired: false,
      reindexReason: null,
    },
    activeJob: null,
    fetchedAt: new Date(120_000),
    ...overrides,
  };
}

describe("statusCopy", () => {
  it("formats intermediate runtime states with progress", () => {
    expect(formatRuntimeValue(ManagedRuntimeState.downloading(45)).value).toBe("Downloading… 45%");
    expect(formatRuntimeValue(ManagedRuntimeState.verifying()).value).toBe("Verifying…");
    expect(formatRuntimeValue(ManagedRuntimeState.missing()).value).toContain("Download required");
  });

  it("builds status rows matching the analytics wireframe fields", () => {
    const rows = buildStatusRows(sampleStatus());
    expect(rows.map((row) => row.label)).toEqual([
      "Prometheus runtime",
      "Prometheus service",
      "Vector index",
      "Ollama",
      "LLM",
      "Documents",
      "Chunks",
      "Last indexed",
    ]);
    expect(rows.find((row) => row.id === "runtime")?.value).toBe("Installed (v1.2.0)");
    expect(rows.find((row) => row.id === "documents")?.value).toBe("4,169");
    expect(rows.find((row) => row.id === "lastIndexed")?.value).toBe("2 minutes ago");
  });

  it("maps recommended actions to button labels", () => {
    expect(runtimeActionLabel("download")).toBe("Download runtime");
    expect(runtimeActionLabel("restart")).toBe("Restart runtime");
    expect(runtimeActionLabel("none")).toBeNull();
    expect(indexActionLabel("reindex")).toBe("Reindex vault");
    expect(indexActionLabel("wait")).toBeNull();
  });
});
