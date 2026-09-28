import { describe, expect, it } from "vitest";

import { formatStatusBarLabel } from "../../../../../src/adapters/inbound/obsidian/status/formatStatusBarLabel";
import { IndexStatus } from "../../../../../src/domain/entities/IndexStatus";
import {
  createRuntimeStatus,
  ManagedRuntimeState,
  OllamaState,
} from "../../../../../src/domain/entities/RuntimeStatus";
import type { SystemStatus } from "../../../../../src/application/dto/system";
import type { IndexStatus as IndexStatusUnion } from "../../../../../src/domain/entities/IndexStatus";
import type {
  ManagedRuntimeState as ManagedRuntimeStateType,
  OllamaState as OllamaStateType,
} from "../../../../../src/domain/entities/RuntimeStatus";

function status(partial: {
  runtime?: ManagedRuntimeStateType;
  index?: IndexStatusUnion;
  ollama?: OllamaStateType;
}): SystemStatus {
  return {
    runtime: createRuntimeStatus({
      runtime: partial.runtime ?? ManagedRuntimeState.running("0.1.0"),
      ollama: partial.ollama ?? OllamaState.running(),
      selectedModel: { name: "qwen3:4b", installed: true },
    }),
    index:
      partial.index ??
      IndexStatus.ready({
        documentCount: 1,
        chunkCount: 1,
        lastIndexedAt: null,
        indexSizeBytes: 1,
      }),
    service: null,
    activeJob: null,
    fetchedAt: new Date(0),
  };
}

describe("formatStatusBarLabel", () => {
  it("shows ready when runtime and index are healthy", () => {
    expect(formatStatusBarLabel(status({}), "none", "none")).toEqual({
      kind: "ready",
      text: "Prometheus: Ready",
    });
  });

  it("shows indexing progress", () => {
    expect(
      formatStatusBarLabel(status({ index: IndexStatus.indexing(42) }), "none", "wait"),
    ).toEqual({
      kind: "indexing",
      text: "Prometheus: Indexing 42%",
    });
  });

  it("shows error for problem states", () => {
    expect(
      formatStatusBarLabel(
        status({ runtime: ManagedRuntimeState.missing() }),
        "download",
        "reindex",
      ),
    ).toEqual({
      kind: "error",
      text: "Prometheus: Error",
    });
  });

  it("shows busy placeholder when status is null", () => {
    expect(formatStatusBarLabel(null, "none", "none")).toEqual({
      kind: "busy",
      text: "Prometheus…",
    });
  });
});
