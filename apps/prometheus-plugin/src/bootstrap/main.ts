import { Plugin } from "obsidian";

import { ObsidianNotifier } from "../adapters/inbound/notifier/ObsidianNotifier";
import { activateChatView } from "../adapters/inbound/obsidian/views/activateChatView";
import { activateSearchView } from "../adapters/inbound/obsidian/views/activateSearchView";
import { activateStatusView } from "../adapters/inbound/obsidian/views/activateStatusView";
import { CHAT_VIEW_TYPE, ChatView } from "../adapters/inbound/obsidian/views/ChatView";
import { SEARCH_VIEW_TYPE, SearchView } from "../adapters/inbound/obsidian/views/SearchView";
import { STATUS_VIEW_TYPE, StatusView } from "../adapters/inbound/obsidian/views/StatusView";
import { formatStatusBarLabel } from "../adapters/inbound/obsidian/status/formatStatusBarLabel";
import { ensureVaultId, ObsidianSettingsRepository } from "../adapters/outbound/settings";
import { wireChat } from "./wireChat";
import { wireIndexing } from "./wireIndexing";
import { wireOnboarding } from "./wireOnboarding";
import { createChatScopeResolver, wireSearch } from "./wireSearch";
import { wireRuntimeLifecycle } from "./wireRuntimeLifecycle";
import { wireStatus } from "./wireStatus";

/**
 * Composition root for the Prometheus Obsidian plugin.
 */
export default class PrometheusPlugin extends Plugin {
  private disposeRuntimeLifecycle: (() => void) | null = null;
  private disposeChat: (() => void) | null = null;
  private disposeSearch: (() => void) | null = null;
  private disposeIndexing: (() => void) | null = null;
  private disposeStatus: (() => void) | null = null;
  private disposeStatusBar: (() => void) | null = null;

  override async onload(): Promise<void> {
    const settings = new ObsidianSettingsRepository(this);
    await ensureVaultId(settings);
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

    const indexing = wireIndexing({
      vault: search.vault,
      rag: runtime.rag,
      settings,
      notifier,
    });
    this.disposeIndexing = indexing.dispose;

    const status = wireStatus({
      rag: runtime.rag,
      runtimeGateway: runtime.runtimeGateway,
      settings,
      startRuntime: runtime.startRuntime,
      jobRegistry: indexing.jobRegistry,
      indexing,
    });
    this.disposeStatus = status.dispose;

    const onboarding = wireOnboarding({
      settings,
      runtimeGateway: runtime.runtimeGateway,
      rag: runtime.rag,
      startRuntime: runtime.startRuntime,
      getSystemStatus: status.getSystemStatus,
      indexing,
    });

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
    this.registerView(STATUS_VIEW_TYPE, (leaf) => new StatusView(leaf, { store: status.store }));

    this.addRibbonIcon("message-square", "Open Prometheus chat", () => {
      void activateChatView(this.app);
    });
    this.addRibbonIcon("activity", "Open Prometheus status", () => {
      void activateStatusView(this.app);
    });

    const statusBarItem = this.addStatusBarItem();
    statusBarItem.addClass("prometheus-statusbar-item");
    statusBarItem.setText("Prometheus…");
    statusBarItem.addEventListener("click", () => {
      void activateStatusView(this.app);
    });
    this.disposeStatusBar = status.store.subscribe((state) => {
      const label = formatStatusBarLabel(state.status, state.runtimeAction, state.indexAction);
      statusBarItem.setText(label.text);
      statusBarItem.toggleClass("prometheus-statusbar-item--ready", label.kind === "ready");
      statusBarItem.toggleClass("prometheus-statusbar-item--indexing", label.kind === "indexing");
      statusBarItem.toggleClass("prometheus-statusbar-item--error", label.kind === "error");
      statusBarItem.toggleClass("prometheus-statusbar-item--busy", label.kind === "busy");
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

    this.addCommand({
      id: "open-status",
      name: "Open status",
      callback: () => {
        void activateStatusView(this.app);
      },
    });

    this.addCommand({
      id: "open-onboarding-wizard",
      name: "Open setup wizard",
      callback: () => {
        onboarding.openOnboarding(this.app);
      },
    });

    this.app.workspace.onLayoutReady(() => {
      void onboarding.openOnboardingIfNeeded(this.app);
    });
  }

  override onunload(): void {
    this.disposeStatusBar?.();
    this.disposeStatusBar = null;
    this.disposeChat?.();
    this.disposeChat = null;
    this.disposeSearch?.();
    this.disposeSearch = null;
    this.disposeStatus?.();
    this.disposeStatus = null;
    this.disposeIndexing?.();
    this.disposeIndexing = null;
    this.disposeRuntimeLifecycle?.();
    this.disposeRuntimeLifecycle = null;
  }
}
