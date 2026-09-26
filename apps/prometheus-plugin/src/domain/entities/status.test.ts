import { describe, expect, it } from "vitest";

import {
  IndexStatus,
  recommendedActionForIndex,
  type IndexStatus as IndexStatusType,
} from "./IndexStatus";
import {
  createRuntimeStatus,
  ManagedRuntimeState,
  OllamaState,
  recommendedActionForRuntime,
  transitionRuntimeToRunning,
  type ManagedRuntimeState as ManagedRuntimeStateType,
} from "./RuntimeStatus";

describe("IndexStatus", () => {
  it("covers every kind with a recommended action", () => {
    const cases: Array<[IndexStatusType, "reindex" | "wait" | "none"]> = [
      [IndexStatus.notIndexed(), "reindex"],
      [IndexStatus.indexing(40), "wait"],
      [
        IndexStatus.ready({
          documentCount: 1,
          chunkCount: 2,
          lastIndexedAt: null,
          indexSizeBytes: 10,
        }),
        "none",
      ],
      [IndexStatus.reindexRequired("embedding changed"), "reindex"],
      [IndexStatus.corrupted("checksum"), "reindex"],
    ];

    for (const [status, action] of cases) {
      expect(recommendedActionForIndex(status)).toBe(action);
    }
  });
});

describe("RuntimeStatus", () => {
  it("covers every managed runtime kind with a recommended action", () => {
    const cases: Array<[ManagedRuntimeStateType, string]> = [
      [ManagedRuntimeState.missing(), "download"],
      [ManagedRuntimeState.downloading(45), "wait"],
      [ManagedRuntimeState.verifying(), "wait"],
      [ManagedRuntimeState.incompatible("0.0.1", ">=0.1.0,<0.2.0"), "updateRuntime"],
      [ManagedRuntimeState.starting(), "wait"],
      [ManagedRuntimeState.running("0.1.0"), "none"],
      [ManagedRuntimeState.stopped(), "restart"],
    ];

    for (const [state, action] of cases) {
      expect(recommendedActionForRuntime(state)).toBe(action);
    }
  });

  it("models the missing → downloading → verifying → running transition", () => {
    const steps = transitionRuntimeToRunning(ManagedRuntimeState.missing(), "0.1.0");
    expect(steps.map((step) => step.kind)).toEqual([
      "missing",
      "downloading",
      "verifying",
      "starting",
      "running",
    ]);
  });

  it("aggregates runtime, ollama, and selected model", () => {
    const status = createRuntimeStatus({
      runtime: ManagedRuntimeState.running("0.1.0"),
      ollama: OllamaState.running(),
      selectedModel: { name: "qwen3:4b", installed: true },
    });
    expect(status.runtime.kind).toBe("running");
    expect(status.ollama.kind).toBe("running");
    expect(status.selectedModel?.name).toBe("qwen3:4b");
  });
});
