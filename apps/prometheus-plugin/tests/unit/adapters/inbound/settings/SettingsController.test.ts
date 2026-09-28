import { describe, expect, it, vi } from "vitest";

import { SettingsController } from "../../../../../src/adapters/inbound/obsidian/settings/SettingsController";
import type { StatusViewState } from "../../../../../src/adapters/inbound/obsidian/status/StatusStore";
import { DEFAULT_PLUGIN_SETTINGS } from "../../../../../src/application/dto/settings";
import { IndexStatus } from "../../../../../src/domain/entities/IndexStatus";
import {
  createRuntimeStatus,
  ManagedRuntimeState,
  OllamaState,
} from "../../../../../src/domain/entities/RuntimeStatus";
import { NetworkAccessDisabledError } from "../../../../../src/domain/errors";
import { FakeNotifier } from "../../../../fakes/FakeNotifier";
import { FakeRuntimeGateway } from "../../../../fakes/FakeRuntimeGateway";
import { FakeSettingsRepository } from "../../../../fakes/FakeSettingsRepository";

function statusState(runtime = ManagedRuntimeState.running("0.1.0")): StatusViewState {
  return {
    status: {
      runtime: createRuntimeStatus({
        runtime,
        ollama: OllamaState.running(),
        selectedModel: { name: "qwen3:4b", installed: true },
      }),
      index: IndexStatus.ready({
        documentCount: 1,
        chunkCount: 1,
        lastIndexedAt: null,
        indexSizeBytes: 1024,
      }),
      service: {
        runtimeVersion: "0.1.0",
        apiVersion: "v1",
        indexState: "ready",
        llmAvailable: true,
        llmModel: "qwen3:4b",
        documentCount: 1,
        chunkCount: 1,
        lastIndexedAt: null,
        indexSizeBytes: 1024,
        reindexRequired: false,
        reindexReason: null,
      },
      activeJob: null,
      fetchedAt: new Date(0),
    },
    runtimeAction: "none",
    indexAction: "none",
    models: [],
    actionBusy: false,
    actionError: null,
    indexingProgress: null,
    installState: null,
  };
}

describe("SettingsController", () => {
  it("rejects invalid custom binary paths", async () => {
    const settings = new FakeSettingsRepository({
      ...DEFAULT_PLUGIN_SETTINGS,
      vaultId: "vault-a1",
    });
    const runtime = new FakeRuntimeGateway();
    runtime.setLocateResult("missing");
    const notifier = new FakeNotifier();
    const controller = new SettingsController({
      settings,
      notifier,
      runtimeGateway: runtime,
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
      stopRuntime: {
        execute: async () => ({ runtime: ManagedRuntimeState.stopped(), stopped: true }),
      },
      selectLlmModel: {
        list: async () => [],
        select: async (name) => ({ models: [], selected: name, requiresRuntimeRestart: false }),
      },
      applyIgnoredFolderChange: { execute: async () => 0 },
      startReindex: async () => ({
        kind: "started" as const,
        job: { jobId: "j", status: "completed", progress: 1, error: null },
        reindexRequired: false,
        reindexReason: null,
      }),
      statusStore: {
        subscribe: (listener) => {
          listener(statusState());
          return () => undefined;
        },
        getState: () => statusState(),
      },
      autoIndexing: { setEnabled: () => undefined, updateDebounce: () => undefined },
      folderExists: () => true,
      bundledReleaseVersion: "0.1.0",
    });

    await controller.updateCustomBinaryPath("/no/such/binary");
    expect((await settings.get()).customBinaryPath).toBeNull();
    expect(notifier.records.some((r) => r.level === "warning")).toBe(true);
    controller.dispose();
  });

  it("toggles autoIndexing and network access", async () => {
    const settings = new FakeSettingsRepository({
      ...DEFAULT_PLUGIN_SETTINGS,
      vaultId: "vault-a1",
    });
    const setEnabled = vi.fn();
    const controller = new SettingsController({
      settings,
      notifier: new FakeNotifier(),
      runtimeGateway: new FakeRuntimeGateway(),
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
      stopRuntime: {
        execute: async () => ({ runtime: ManagedRuntimeState.stopped(), stopped: true }),
      },
      selectLlmModel: {
        list: async () => [{ name: "qwen3:4b", installed: true, sizeBytes: 1, quantization: null }],
        select: async (name) => ({
          models: [{ name, installed: true, sizeBytes: 1, quantization: null }],
          selected: name,
          requiresRuntimeRestart: true,
        }),
      },
      applyIgnoredFolderChange: { execute: async () => 0 },
      startReindex: async () => ({
        kind: "started" as const,
        job: { jobId: "j", status: "completed", progress: 1, error: null },
        reindexRequired: false,
        reindexReason: null,
      }),
      statusStore: {
        subscribe: (listener) => {
          listener(statusState());
          return () => undefined;
        },
        getState: () => statusState(),
      },
      autoIndexing: { setEnabled, updateDebounce: () => undefined },
      folderExists: () => true,
      bundledReleaseVersion: "0.1.0",
    });

    await controller.setAutoIndexing(false);
    expect(setEnabled).toHaveBeenCalledWith(false);
    expect((await settings.get()).autoIndexing).toBe(false);

    await controller.setNetworkAccess("disabled");
    expect((await settings.get()).networkAccess).toBe("disabled");

    await controller.selectModel("qwen3:4b");
    expect((await settings.get()).llmModel).toBe("qwen3:4b");
    controller.dispose();
  });

  it("adds ignored folders and applies folder change", async () => {
    const settings = new FakeSettingsRepository({
      ...DEFAULT_PLUGIN_SETTINGS,
      vaultId: "vault-a1",
      ignoredFolders: [],
    });
    const apply = vi.fn(async () => 2);
    const notifier = new FakeNotifier();
    const controller = new SettingsController({
      settings,
      notifier,
      runtimeGateway: new FakeRuntimeGateway(),
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
      stopRuntime: {
        execute: async () => ({ runtime: ManagedRuntimeState.stopped(), stopped: true }),
      },
      selectLlmModel: {
        list: async () => [],
        select: async (name) => ({ models: [], selected: name, requiresRuntimeRestart: false }),
      },
      applyIgnoredFolderChange: { execute: apply },
      startReindex: async () => ({
        kind: "started" as const,
        job: { jobId: "j", status: "completed", progress: 1, error: null },
        reindexRequired: false,
        reindexReason: null,
      }),
      statusStore: {
        subscribe: (listener) => {
          listener(statusState());
          return () => undefined;
        },
        getState: () => statusState(),
      },
      autoIndexing: { setEnabled: () => undefined, updateDebounce: () => undefined },
      folderExists: () => true,
      bundledReleaseVersion: "0.1.0",
    });

    await controller.addIgnoredFolder("Archive");
    expect((await settings.get()).ignoredFolders).toEqual(["Archive/"]);
    expect(apply).toHaveBeenCalledOnce();
    expect(notifier.records.some((r) => r.level === "info")).toBe(true);
    controller.dispose();
  });

  it("surfaces network-disabled install errors", async () => {
    const notifier = new FakeNotifier();
    const controller = new SettingsController({
      settings: new FakeSettingsRepository({
        ...DEFAULT_PLUGIN_SETTINGS,
        vaultId: "vault-a1",
        networkAccess: "disabled",
      }),
      notifier,
      runtimeGateway: new FakeRuntimeGateway(),
      installRuntime: {
        execute: async () => {
          throw new NetworkAccessDisabledError();
        },
      },
      startRuntime: {
        execute: async () => ({
          kind: "ready" as const,
          runtime: ManagedRuntimeState.running("0.1.0"),
          connection: { baseUrl: "http://127.0.0.1:1", sessionToken: "t" },
          ownership: "owned" as const,
          spawned: true,
        }),
      },
      stopRuntime: {
        execute: async () => ({ runtime: ManagedRuntimeState.stopped(), stopped: true }),
      },
      selectLlmModel: {
        list: async () => [],
        select: async (name) => ({ models: [], selected: name, requiresRuntimeRestart: false }),
      },
      applyIgnoredFolderChange: { execute: async () => 0 },
      startReindex: async () => ({
        kind: "started" as const,
        job: { jobId: "j", status: "completed", progress: 1, error: null },
        reindexRequired: false,
        reindexReason: null,
      }),
      statusStore: {
        subscribe: (listener) => {
          listener(statusState(ManagedRuntimeState.missing()));
          return () => undefined;
        },
        getState: () => statusState(ManagedRuntimeState.missing()),
      },
      autoIndexing: { setEnabled: () => undefined, updateDebounce: () => undefined },
      folderExists: () => true,
      bundledReleaseVersion: "0.1.0",
    });

    await controller.installOrUpdateRuntime();
    expect(controller.getState().actionError).toContain("network access is disabled");
    expect(notifier.records.some((r) => r.level === "error")).toBe(true);
    controller.dispose();
  });

  it("rejects invalid ollama addresses", async () => {
    const settings = new FakeSettingsRepository({
      ...DEFAULT_PLUGIN_SETTINGS,
      vaultId: "vault-a1",
    });
    const notifier = new FakeNotifier();
    const controller = new SettingsController({
      settings,
      notifier,
      runtimeGateway: new FakeRuntimeGateway(),
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
      stopRuntime: {
        execute: async () => ({ runtime: ManagedRuntimeState.stopped(), stopped: true }),
      },
      selectLlmModel: {
        list: async () => [],
        select: async (name) => ({ models: [], selected: name, requiresRuntimeRestart: false }),
      },
      applyIgnoredFolderChange: { execute: async () => 0 },
      startReindex: async () => ({
        kind: "started" as const,
        job: { jobId: "j", status: "completed", progress: 1, error: null },
        reindexRequired: false,
        reindexReason: null,
      }),
      statusStore: {
        subscribe: (listener) => {
          listener(statusState());
          return () => undefined;
        },
        getState: () => statusState(),
      },
      autoIndexing: { setEnabled: () => undefined, updateDebounce: () => undefined },
      folderExists: () => true,
      bundledReleaseVersion: "0.1.0",
    });

    await controller.updateOllamaAddress("not-a-host");
    expect((await settings.get()).ollamaAddress).toBe("127.0.0.1:11434");
    expect(notifier.records.some((r) => r.level === "warning")).toBe(true);
    controller.dispose();
  });
});
