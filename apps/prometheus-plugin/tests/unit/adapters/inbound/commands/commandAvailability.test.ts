import { describe, expect, it } from "vitest";

import {
  canReindexVault,
  canRestartRuntime,
} from "../../../../../src/adapters/inbound/obsidian/commands/commandAvailability";
import type { StatusViewState } from "../../../../../src/adapters/inbound/obsidian/status/StatusStore";
import type { SystemStatus } from "../../../../../src/application/dto/system";
import {
  IndexStatus,
  type IndexStatus as IndexStatusType,
} from "../../../../../src/domain/entities/IndexStatus";
import {
  ManagedRuntimeState,
  OllamaState,
  createRuntimeStatus,
  type ManagedRuntimeState as ManagedRuntimeStateType,
} from "../../../../../src/domain/entities/RuntimeStatus";

function baseStatus(overrides: {
  runtime?: ManagedRuntimeStateType;
  index?: IndexStatusType;
}): SystemStatus {
  return {
    runtime: createRuntimeStatus({
      runtime: overrides.runtime ?? ManagedRuntimeState.running("1.0.0"),
      ollama: OllamaState.running(),
    }),
    index:
      overrides.index ??
      IndexStatus.ready({
        documentCount: 1,
        chunkCount: 1,
        lastIndexedAt: null,
        indexSizeBytes: 100,
      }),
    service: null,
    activeJob: null,
    fetchedAt: new Date(0),
  };
}

function state(
  partial: Partial<StatusViewState> & { status?: SystemStatus | null },
): StatusViewState {
  return {
    status: partial.status === undefined ? baseStatus({}) : partial.status,
    runtimeAction: partial.runtimeAction ?? "none",
    indexAction: partial.indexAction ?? "none",
    models: partial.models ?? [],
    actionBusy: partial.actionBusy ?? false,
    actionError: partial.actionError ?? null,
    indexingProgress: partial.indexingProgress ?? null,
    installState: partial.installState ?? null,
  };
}

describe("canReindexVault", () => {
  it("returns false when busy or status is null", () => {
    expect(canReindexVault(state({ actionBusy: true, indexAction: "reindex" }))).toBe(false);
    expect(canReindexVault(state({ status: null, indexAction: "reindex" }))).toBe(false);
  });

  it("returns false while index action is wait", () => {
    expect(
      canReindexVault(
        state({
          indexAction: "wait",
          status: baseStatus({ index: IndexStatus.indexing(50) }),
        }),
      ),
    ).toBe(false);
  });

  it("returns true when idle and index is not waiting", () => {
    expect(canReindexVault(state({ indexAction: "none" }))).toBe(true);
    expect(canReindexVault(state({ indexAction: "reindex" }))).toBe(true);
  });
});

describe("canRestartRuntime", () => {
  it("returns false when busy or status is null", () => {
    expect(canRestartRuntime(state({ actionBusy: true }))).toBe(false);
    expect(canRestartRuntime(state({ status: null }))).toBe(false);
  });

  it("returns true for running and stopped runtimes", () => {
    expect(
      canRestartRuntime(
        state({ status: baseStatus({ runtime: ManagedRuntimeState.running("1.0.0") }) }),
      ),
    ).toBe(true);
    expect(
      canRestartRuntime(
        state({ status: baseStatus({ runtime: ManagedRuntimeState.stopped("requested") }) }),
      ),
    ).toBe(true);
  });

  it("returns false for missing, downloading, and incompatible runtimes", () => {
    expect(
      canRestartRuntime(state({ status: baseStatus({ runtime: ManagedRuntimeState.missing() }) })),
    ).toBe(false);
    expect(
      canRestartRuntime(
        state({ status: baseStatus({ runtime: ManagedRuntimeState.downloading(10) }) }),
      ),
    ).toBe(false);
    expect(
      canRestartRuntime(
        state({
          status: baseStatus({
            runtime: ManagedRuntimeState.incompatible("0.9.0", ">=1.0.0"),
          }),
        }),
      ),
    ).toBe(false);
  });
});
