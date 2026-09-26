import { Plugin } from "obsidian";

import { ObsidianNotifier } from "../adapters/inbound/notifier/ObsidianNotifier";
import { activateChatView } from "../adapters/inbound/obsidian/views/activateChatView";
import { CHAT_VIEW_TYPE, ChatView } from "../adapters/inbound/obsidian/views/ChatView";
import { ObsidianSettingsRepository } from "../adapters/outbound/settings";
import { wireChat } from "./wireChat";
import { wireRuntimeLifecycle } from "./wireRuntimeLifecycle";

/**
 * Composition root for the Prometheus Obsidian plugin.
 */
export default class PrometheusPlugin extends Plugin {
  private disposeRuntimeLifecycle: (() => void) | null = null;
  private disposeChat: (() => void) | null = null;

  override async onload(): Promise<void> {
    const settings = new ObsidianSettingsRepository(this);
    const notifier = new ObsidianNotifier();
    const runtime = wireRuntimeLifecycle({
      settings,
      notifier,
    });
    this.disposeRuntimeLifecycle = runtime.dispose;

    const chat = wireChat({
      app: this.app,
      settings,
      rag: runtime.rag,
      startRuntime: runtime.startRuntime,
      notifier,
    });
    this.disposeChat = chat.dispose;

    this.registerView(CHAT_VIEW_TYPE, (leaf) => new ChatView(leaf, { store: chat.store }));

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
  }

  override onunload(): void {
    this.disposeChat?.();
    this.disposeChat = null;
    this.disposeRuntimeLifecycle?.();
    this.disposeRuntimeLifecycle = null;
  }
}
