import { describe, expect, it, vi } from "vitest";

import type { App, Command, Plugin } from "obsidian";

import { registerCommands } from "../../../../../src/adapters/inbound/obsidian/commands/registerCommands";
import type { StatusViewState } from "../../../../../src/adapters/inbound/obsidian/status/StatusStore";
import type { SystemStatus } from "../../../../../src/application/dto/system";
import { IndexStatus } from "../../../../../src/domain/entities/IndexStatus";
import {
  ManagedRuntimeState,
  OllamaState,
  createRuntimeStatus,
} from "../../../../../src/domain/entities/RuntimeStatus";

function statusState(partial: Partial<StatusViewState> = {}): StatusViewState {
  const status: SystemStatus = {
    runtime: createRuntimeStatus({
      runtime: ManagedRuntimeState.running("1.0.0"),
      ollama: OllamaState.running(),
    }),
    index: IndexStatus.ready({
      documentCount: 1,
      chunkCount: 1,
      lastIndexedAt: null,
      indexSizeBytes: 100,
    }),
    service: null,
    activeJob: null,
    fetchedAt: new Date(0),
  };
  return {
    status: partial.status === undefined ? status : partial.status,
    runtimeAction: partial.runtimeAction ?? "none",
    indexAction: partial.indexAction ?? "none",
    models: [],
    actionBusy: partial.actionBusy ?? false,
    actionError: null,
    indexingProgress: null,
    installState: null,
  };
}

function createFakePlugin() {
  const commands: Command[] = [];
  const plugin = {
    addCommand: (command: Command) => {
      commands.push(command);
      return command;
    },
  } as unknown as Plugin;
  return { commands, plugin };
}

describe("registerCommands", () => {
  it("registers commands without default hotkeys", () => {
    const { plugin, commands } = createFakePlugin();
    const statusStore = {
      getState: () => statusState(),
      reindex: vi.fn(async () => undefined),
      restartRuntime: vi.fn(async () => undefined),
    };
    registerCommands(plugin, {
      app: {} as App,
      chatStore: { clear: vi.fn() },
      statusStore,
      openOnboarding: vi.fn(),
      openDiagnostics: vi.fn(),
      activateChat: vi.fn(),
      activateSearch: vi.fn(),
      activateStatus: vi.fn(),
    });

    expect(commands).toHaveLength(8);
    for (const command of commands) {
      expect("hotkeys" in command ? command.hotkeys : undefined).toBeUndefined();
    }
    expect(commands.map((c) => c.id)).toEqual([
      "open-chat",
      "clear-chat-session",
      "open-search",
      "open-status",
      "open-onboarding-wizard",
      "open-diagnostics",
      "reindex-vault",
      "restart-runtime",
    ]);
  });

  it("gates reindex and restart via checkCallback", () => {
    const { plugin, commands } = createFakePlugin();
    let current = statusState({ actionBusy: true });
    const statusStore = {
      getState: () => current,
      reindex: vi.fn(async () => undefined),
      restartRuntime: vi.fn(async () => undefined),
    };
    registerCommands(plugin, {
      app: {} as App,
      chatStore: { clear: vi.fn() },
      statusStore,
      openOnboarding: vi.fn(),
      openDiagnostics: vi.fn(),
      activateChat: vi.fn(),
      activateSearch: vi.fn(),
      activateStatus: vi.fn(),
    });

    const reindex = commands.find((c) => c.id === "reindex-vault");
    const restart = commands.find((c) => c.id === "restart-runtime");
    expect(reindex?.checkCallback?.(true)).toBe(false);
    expect(restart?.checkCallback?.(true)).toBe(false);

    current = statusState({ actionBusy: false, indexAction: "none" });
    expect(reindex?.checkCallback?.(true)).toBe(true);
    expect(restart?.checkCallback?.(true)).toBe(true);
    reindex?.checkCallback?.(false);
    restart?.checkCallback?.(false);
    expect(statusStore.reindex).toHaveBeenCalledTimes(1);
    expect(statusStore.restartRuntime).toHaveBeenCalledTimes(1);
  });
});
