import { Plugin } from "obsidian";

import { ObsidianNotifier } from "../adapters/inbound/notifier/ObsidianNotifier";
import { activateChatView } from "../adapters/inbound/obsidian/views/activateChatView";
import { activateSearchView } from "../adapters/inbound/obsidian/views/activateSearchView";
import { CHAT_VIEW_TYPE, ChatView } from "../adapters/inbound/obsidian/views/ChatView";
import { SEARCH_VIEW_TYPE, SearchView } from "../adapters/inbound/obsidian/views/SearchView";
import { ObsidianSettingsRepository } from "../adapters/outbound/settings";
import { wireChat } from "./wireChat";
import { createChatScopeResolver, wireSearch } from "./wireSearch";
import { wireRuntimeLifecycle } from "./wireRuntimeLifecycle";

/**
 * Composition root for the Prometheus Obsidian plugin.
 */
export default class PrometheusPlugin extends Plugin {
  private disposeRuntimeLifecycle: (() => void) | null = null;
  private disposeChat: (() => void) | null = null;
  private disposeSearch: (() => void) | null = null;

  override async onload(): Promise<void> {
    const settings = new ObsidianSettingsRepository(this);
    const notifier = new ObsidianNotifier();
    const runtime = wireRuntimeLifecycle({
      settings,
      notifier,
    });
    this.disposeRuntimeLifecycle = runtime.dispose;

    const search = wireSearch({
      app: this.app,
      settings,
      rag: runtime.rag,
      startRuntime: runtime.startRuntime,
      notifier,
    });
    this.disposeSearch = search.dispose;

    const chat = wireChat({
      app: this.app,
      settings,
      rag: runtime.rag,
      startRuntime: runtime.startRuntime,
      notifier,
      vault: search.vault,
      resolveScope: createChatScopeResolver({ settings, vault: search.vault }),
    });
    this.disposeChat = chat.dispose;

    this.registerView(CHAT_VIEW_TYPE, (leaf) => new ChatView(leaf, { store: chat.store }));
    this.registerView(SEARCH_VIEW_TYPE, (leaf) => new SearchView(leaf, { store: search.store }));

    this.addRibbonIcon("message-square", "Open Prometheus chat", () => {
      void activateChatView(this.app);
    });

    this.addCommand({
      id: "open-chat",
      name: "Open chat",
      callback: () => {
        void activateChatView(this.app);
      },
    });

    this.addCommand({
      id: "clear-chat-session",
      name: "Clear chat session",
      callback: () => {
        chat.store.clear();
      },
    });

    this.addCommand({
      id: "open-search",
      name: "Open semantic search",
      callback: () => {
        void activateSearchView(this.app);
      },
    });
  }

  override onunload(): void {
    this.disposeChat?.();
    this.disposeChat = null;
    this.disposeSearch?.();
    this.disposeSearch = null;
    this.disposeRuntimeLifecycle?.();
    this.disposeRuntimeLifecycle = null;
  }
}
