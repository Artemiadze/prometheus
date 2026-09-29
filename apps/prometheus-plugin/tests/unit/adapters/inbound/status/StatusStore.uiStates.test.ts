import { describe, expect, it } from "vitest";

import type { StatusStoreDeps } from "../../../../../src/adapters/inbound/obsidian/status/StatusStore";
import { StatusStore } from "../../../../../src/adapters/inbound/obsidian/status/StatusStore";
import type { SystemStatus } from "../../../../../src/application/dto/system";
import { IndexStatus } from "../../../../../src/domain/entities/IndexStatus";
import {
  createRuntimeStatus,
  ManagedRuntimeState,
  OllamaState,
} from "../../../../../src/domain/entities/RuntimeStatus";
import { FakeClock } from "../../../../fakes/FakeClock";

function makeStatus(runtime = ManagedRuntimeState.running("0.1.0")): SystemStatus {
  return {
    runtime: createRuntimeStatus({
      runtime,
      ollama: OllamaState.running(),
      selectedModel: { name: "qwen3:4b", installed: true },
    }),
    index: IndexStatus.ready({
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

function baseDeps(overrides: Partial<StatusStoreDeps> = {}): StatusStoreDeps {
  return {
    getSystemStatus: {
      execute: async () => makeStatus(),
      poll: async () => undefined,
    },
    installRuntime: { execute: async () => ManagedRuntimeState.verifying() },
    startRuntime: {
      execute: async () => ({
        kind: "ready" as const,
        runtime: ManagedRuntimeState.running("0.1.0"),
        connection: { baseUrl: "http://127.0.0.1:1", sessionToken: "t" },
        ownership: "owned" as const,
        spawned: true,
      }),
    },
    selectLlmModel: {
      list: async () => [{ name: "qwen3:4b", sizeBytes: 1, quantization: "Q4", installed: true }],
      select: async (name: string) => ({
        models: [],
        selected: name,
        requiresRuntimeRestart: false,
      }),
    },
    startInitialSync: async () => ({
      job: { jobId: "j", status: "completed" as const, progress: 1, error: null },
      failures: [],
    }),
    startReindex: async () => ({
      kind: "started" as const,
      job: { jobId: "j", status: "completed" as const, progress: 1, error: null },
      reindexRequired: false,
      reindexReason: null,
    }),
    cancelActive: async () => null,
    pollIntervalMs: 1000,
    ...overrides,
  };
}

/**
 * PLG-85 — StatusStore UI states without Obsidian DOM.
 * Covers idle (no poll), loading (actionBusy), error, empty/missing runtime, and success.
 */
describe("StatusStore UI states (PLG-85)", () => {
  it("starts idle with null status before polling (empty)", () => {
    const store = new StatusStore(baseDeps());
    expect(store.isPolling()).toBe(false);
    expect(store.getState().status).toBeNull();
    expect(store.getState().actionBusy).toBe(false);
    expect(store.getState().actionError).toBeNull();
    store.dispose();
  });

  it("loads success status after startPolling", async () => {
    const clock = new FakeClock();
    const store = new StatusStore(
      baseDeps({
        getSystemStatus: {
          execute: async () => makeStatus(),
          poll: async (onUpdate, signal, intervalMs = 1000) => {
            onUpdate(makeStatus());
            while (!signal?.aborted) {
              await clock.sleep(intervalMs, signal);
              onUpdate(makeStatus());
            }
          },
        },
      }),
    );
    store.startPolling();
    await Promise.resolve();
    expect(store.getState().status?.runtime.runtime.kind).toBe("running");
    expect(store.getState().runtimeAction).toBe("none");
    expect(store.getState().indexAction).toBe("none");
    store.dispose();
  });

  it("sets actionBusy while restart runs (loading) then clears", async () => {
    let resolveStart: () => void = () => undefined;
    const store = new StatusStore(
      baseDeps({
        startRuntime: {
          execute: () =>
            new Promise((resolve) => {
              resolveStart = () =>
                resolve({
                  kind: "ready" as const,
                  runtime: ManagedRuntimeState.running("0.1.0"),
                  connection: { baseUrl: "http://127.0.0.1:1", sessionToken: "t" },
                  ownership: "owned" as const,
                  spawned: true,
                });
            }),
        },
      }),
    );

    const pending = store.restartRuntime();
    await Promise.resolve();
    expect(store.getState().actionBusy).toBe(true);

    resolveStart();
    await pending;
    expect(store.getState().actionBusy).toBe(false);
    store.dispose();
  });

  it("maps action failures to actionError", async () => {
    const store = new StatusStore(
      baseDeps({
        startRuntime: {
          execute: async () => {
            throw new Error("spawn failed");
          },
        },
      }),
    );
    await store.restartRuntime();
    expect(store.getState().actionBusy).toBe(false);
    expect(store.getState().actionError).toBeTruthy();
    store.dispose();
  });

  it("derives download action when runtime is missing", async () => {
    const clock = new FakeClock();
    const store = new StatusStore(
      baseDeps({
        getSystemStatus: {
          execute: async () => makeStatus(ManagedRuntimeState.missing()),
          poll: async (onUpdate, signal, intervalMs = 1000) => {
            onUpdate(makeStatus(ManagedRuntimeState.missing()));
            while (!signal?.aborted) {
              await clock.sleep(intervalMs, signal);
            }
          },
        },
      }),
    );
    store.startPolling();
    await Promise.resolve();
    expect(store.getState().runtimeAction).toBe("download");
    store.dispose();
  });
});
