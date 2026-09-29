import { describe, expect, it, vi } from "vitest";

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

describe("StatusStore", () => {
  it("derives recommended actions from polled status", async () => {
    const clock = new FakeClock();
    let current = makeStatus(ManagedRuntimeState.missing());
    const store = new StatusStore({
      getSystemStatus: {
        execute: async () => current,
        poll: async (onUpdate, signal, intervalMs = 1000) => {
          onUpdate(current);
          while (!signal?.aborted) {
            await clock.sleep(intervalMs, signal);
            onUpdate(current);
          }
        },
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
        list: async () => [],
        select: async (name) => ({
          models: [],
          selected: name,
          requiresRuntimeRestart: false,
        }),
      },
      startInitialSync: async () => ({
        job: { jobId: "j", status: "completed", progress: 1, error: null },
        failures: [],
      }),
      startReindex: async () => ({
        kind: "started" as const,
        job: { jobId: "j", status: "completed", progress: 1, error: null },
        reindexRequired: false,
        reindexReason: null,
      }),
      cancelActive: async () => null,
      pollIntervalMs: 1000,
    });

    store.startPolling();
    await Promise.resolve();
    expect(store.getState().runtimeAction).toBe("download");

    current = makeStatus(ManagedRuntimeState.running("0.1.0"));
    clock.advance(1000);
    await Promise.resolve();
    await Promise.resolve();
    expect(store.getState().runtimeAction).toBe("none");

    store.dispose();
  });

  it("does not poll until startPolling", async () => {
    const poll = vi.fn(async () => undefined);
    const store = new StatusStore({
      getSystemStatus: {
        execute: async () => makeStatus(),
        poll,
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
        list: async () => [],
        select: async (name) => ({ models: [], selected: name, requiresRuntimeRestart: false }),
      },
      startInitialSync: async () => ({
        job: { jobId: "j", status: "completed", progress: 1, error: null },
        failures: [],
      }),
      startReindex: async () => ({
        kind: "started" as const,
        job: { jobId: "j", status: "completed", progress: 1, error: null },
        reindexRequired: false,
        reindexReason: null,
      }),
      cancelActive: async () => null,
      pollIntervalMs: 1000,
    });

    await Promise.resolve();
    expect(store.isPolling()).toBe(false);
    expect(poll).not.toHaveBeenCalled();

    store.startPolling();
    expect(store.isPolling()).toBe(true);
    expect(poll).toHaveBeenCalledOnce();
    store.dispose();
  });

  it("installRuntime dispatches download then start", async () => {
    const clock = new FakeClock();
    const install = vi.fn(
      async (onState?: (s: ReturnType<typeof ManagedRuntimeState.downloading>) => void) => {
        onState?.(ManagedRuntimeState.downloading(50));
        return ManagedRuntimeState.verifying();
      },
    );
    const start = vi.fn(async () => ({
      kind: "ready" as const,
      runtime: ManagedRuntimeState.running("0.1.0"),
      connection: { baseUrl: "http://127.0.0.1:1", sessionToken: "t" },
      ownership: "owned" as const,
      spawned: true,
    }));
    const store = new StatusStore({
      getSystemStatus: {
        execute: async () => makeStatus(ManagedRuntimeState.missing()),
        poll: async (onUpdate, signal, intervalMs = 1000) => {
          onUpdate(makeStatus(ManagedRuntimeState.missing()));
          while (!signal?.aborted) {
            await clock.sleep(intervalMs, signal);
          }
        },
      },
      installRuntime: { execute: install },
      startRuntime: { execute: start },
      selectLlmModel: {
        list: async () => [],
        select: async (name) => ({ models: [], selected: name, requiresRuntimeRestart: false }),
      },
      startInitialSync: async () => ({
        job: { jobId: "j", status: "completed", progress: 1, error: null },
        failures: [],
      }),
      startReindex: async () => ({
        kind: "started" as const,
        job: { jobId: "j", status: "completed", progress: 1, error: null },
        reindexRequired: false,
        reindexReason: null,
      }),
      cancelActive: async () => null,
      pollIntervalMs: 1000,
    });

    await store.installRuntime();
    expect(install).toHaveBeenCalledOnce();
    expect(start).toHaveBeenCalledOnce();
    store.dispose();
  });

  it("dispose aborts the poll loop", async () => {
    const clock = new FakeClock();
    let polls = 0;
    const store = new StatusStore({
      getSystemStatus: {
        execute: async () => makeStatus(),
        poll: async (onUpdate, signal, intervalMs = 1000) => {
          while (!signal?.aborted) {
            polls += 1;
            onUpdate(makeStatus());
            await clock.sleep(intervalMs, signal);
          }
        },
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
        list: async () => [],
        select: async (name) => ({ models: [], selected: name, requiresRuntimeRestart: false }),
      },
      startInitialSync: async () => ({
        job: { jobId: "j", status: "completed", progress: 1, error: null },
        failures: [],
      }),
      startReindex: async () => ({
        kind: "started" as const,
        job: { jobId: "j", status: "completed", progress: 1, error: null },
        reindexRequired: false,
        reindexReason: null,
      }),
      cancelActive: async () => null,
      pollIntervalMs: 1000,
    });

    store.startPolling();
    await Promise.resolve();
    const before = polls;
    store.dispose();
    clock.advance(5000);
    await Promise.resolve();
    expect(polls).toBe(before);
  });
});
