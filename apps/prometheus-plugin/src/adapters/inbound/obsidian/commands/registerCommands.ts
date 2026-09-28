import type { App, Plugin } from "obsidian";

import type { ChatStore } from "../chat/ChatStore";
import type { StatusStore } from "../status/StatusStore";
import { canReindexVault, canRestartRuntime } from "./commandAvailability";

export type RegisterCommandsDeps = {
  readonly app: App;
  readonly chatStore: Pick<ChatStore, "clear">;
  readonly statusStore: Pick<StatusStore, "getState" | "reindex" | "restartRuntime">;
  readonly openOnboarding: (app: App) => void;
  readonly activateChat: (app: App) => void | Promise<void>;
  readonly activateSearch: (app: App) => void | Promise<void>;
  readonly activateStatus: (app: App) => void | Promise<void>;
};

export function registerCommands(plugin: Plugin, deps: RegisterCommandsDeps): void {
  plugin.addCommand({
    id: "open-chat",
    name: "Open chat",
    callback: () => {
      void deps.activateChat(deps.app);
    },
  });

  plugin.addCommand({
    id: "clear-chat-session",
    name: "Clear chat session",
    callback: () => {
      deps.chatStore.clear();
    },
  });

  plugin.addCommand({
    id: "open-search",
    name: "Open semantic search",
    callback: () => {
      void deps.activateSearch(deps.app);
    },
  });

  plugin.addCommand({
    id: "open-status",
    name: "Open status",
    callback: () => {
      void deps.activateStatus(deps.app);
    },
  });

  plugin.addCommand({
    id: "open-onboarding-wizard",
    name: "Open setup wizard",
    callback: () => {
      deps.openOnboarding(deps.app);
    },
  });

  plugin.addCommand({
    id: "reindex-vault",
    name: "Reindex vault",
    checkCallback: (checking) => {
      if (!canReindexVault(deps.statusStore.getState())) {
        return false;
      }
      if (!checking) {
        void deps.statusStore.reindex();
      }
      return true;
    },
  });

  plugin.addCommand({
    id: "restart-runtime",
    name: "Restart runtime",
    checkCallback: (checking) => {
      if (!canRestartRuntime(deps.statusStore.getState())) {
        return false;
      }
      if (!checking) {
        void deps.statusStore.restartRuntime();
      }
      return true;
    },
  });
}
