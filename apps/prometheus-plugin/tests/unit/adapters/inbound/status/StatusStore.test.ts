import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StatusStore } from "../../../../../src/adapters/inbound/obsidian/status/StatusStore";
import type { SystemStatus } from "../../../../../src/application/dto/system";
import { IndexStatus } from "../../../../../src/domain/entities/IndexStatus";
import {
  createRuntimeStatus,
  ManagedRuntimeState,
  OllamaState,
} from "../../../../../src/domain/entities/RuntimeStatus";

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
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("derives recommended actions from polled status", async () => {
    let current = makeStatus(ManagedRuntimeState.missing());
    const store = new StatusStore({
      getSystemStatus: {
        execute: async () => current,
        poll: vi.fn(),
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

    store.setActiveUiViews(1);
    store.startPolling();
    await Promise.resolve();
    expect(store.getState().runtimeAction).toBe("download");

    current = makeStatus(ManagedRuntimeState.running("0.1.0"));
    await vi.advanceTimersByTimeAsync(1000);
    expect(store.getState().runtimeAction).toBe("none");

    store.dispose();
  });

  it("does not poll until startPolling", async () => {
    const execute = vi.fn(async () => makeStatus());
    const store = new StatusStore({
      getSystemStatus: {
        execute,
        poll: vi.fn(),
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

    expect(store.isPolling()).toBe(false);
    expect(execute).not.toHaveBeenCalled();

    store.setActiveUiViews(1);
    store.startPolling();
    expect(store.isPolling()).toBe(true);
    await Promise.resolve();
    expect(execute).toHaveBeenCalledOnce();
    store.dispose();
  });

  it("installRuntime dispatches download then start", async () => {
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
        poll: vi.fn(),
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
    let polls = 0;
    const store = new StatusStore({
      getSystemStatus: {
        execute: async () => {
          polls += 1;
          return makeStatus();
        },
        poll: vi.fn(),
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

    store.setActiveUiViews(1);
    store.startPolling();
    await Promise.resolve();
    const before = polls;
    store.dispose();
    await vi.advanceTimersByTimeAsync(5000);
    expect(polls).toBe(before);
  });
});
