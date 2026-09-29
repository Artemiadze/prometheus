import { Plugin } from "obsidian";

import { DedupNotifier } from "../adapters/inbound/notifier/DedupNotifier";
import { ObsidianNotifier } from "../adapters/inbound/notifier/ObsidianNotifier";
import { registerCommands } from "../adapters/inbound/obsidian/commands/registerCommands";
import { registerContextMenu } from "../adapters/inbound/obsidian/commands/registerContextMenu";
import { activateChatView } from "../adapters/inbound/obsidian/views/activateChatView";
import { activateSearchView } from "../adapters/inbound/obsidian/views/activateSearchView";
import { activateStatusView } from "../adapters/inbound/obsidian/views/activateStatusView";
import { CHAT_VIEW_TYPE, ChatView } from "../adapters/inbound/obsidian/views/ChatView";
import { SEARCH_VIEW_TYPE, SearchView } from "../adapters/inbound/obsidian/views/SearchView";
import { STATUS_VIEW_TYPE, StatusView } from "../adapters/inbound/obsidian/views/StatusView";
import { formatStatusBarLabel } from "../adapters/inbound/obsidian/status/formatStatusBarLabel";
import { CompositeLogger, ConsoleLogger, RecentEventsBuffer } from "../adapters/outbound/logging";
import { ensureVaultId, ObsidianSettingsRepository } from "../adapters/outbound/settings";
import { SystemClock } from "../adapters/outbound/system/SystemClock";
import { wireAutoIndexing } from "./wireAutoIndexing";
import { wireChat } from "./wireChat";
import { wireDiagnostics } from "./wireDiagnostics";
import { wireIndexing } from "./wireIndexing";
import { wireOnboarding } from "./wireOnboarding";
import { createChatScopeResolver, wireSearch } from "./wireSearch";
import { wireRuntimeLifecycle } from "./wireRuntimeLifecycle";
import { wireSettingsTab } from "./wireSettingsTab";
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
  private disposeAutoIndexing: (() => void) | null = null;
  private disposeSettings: (() => void) | null = null;

  override async onload(): Promise<void> {
    const clock = new SystemClock();
    const consoleLogger = new ConsoleLogger();
    const recentEvents = new RecentEventsBuffer(clock);
    const logger = new CompositeLogger([consoleLogger, recentEvents], [consoleLogger]);

    const rawNotifier = new ObsidianNotifier();
    const notifier = new DedupNotifier(rawNotifier, clock);
    const settings = new ObsidianSettingsRepository(this, notifier);
    await ensureVaultId(settings);

    const initialSettings = await settings.get();
    logger.setVerbose(initialSettings.verboseLogging);

    const runtime = wireRuntimeLifecycle({
      settings,
      notifier,
      logger,
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

    const autoIndexing = wireAutoIndexing({
      vault: search.vault,
      rag: runtime.rag,
      settings,
      syncState: indexing.syncState,
      notifier,
    });
    this.disposeAutoIndexing = autoIndexing.dispose;

    const status = wireStatus({
      rag: runtime.rag,
      runtimeGateway: runtime.runtimeGateway,
      settings,
      startRuntime: runtime.startRuntime,
      jobRegistry: indexing.jobRegistry,
      indexing,
    });
    this.disposeStatus = status.dispose;

    const diagnostics = wireDiagnostics({
      app: this.app,
      pluginVersion: this.manifest.version,
      runtimeGateway: runtime.runtimeGateway,
      sessions: runtime.sessions,
      settings,
      recentEvents,
      statusStore: status.store,
      notifier,
    });

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

    const settingsTab = wireSettingsTab({
      app: this.app,
      plugin: this,
      settings,
      notifier,
      runtimeGateway: runtime.runtimeGateway,
      rag: runtime.rag,
      startRuntime: runtime.startRuntime,
      stopRuntime: runtime.stopRuntime,
      statusStore: status.store,
      indexing,
      autoIndexing,
      syncState: indexing.syncState,
      setVerboseLogging: (enabled) => {
        logger.setVerbose(enabled);
      },
      openDiagnostics: () => {
        diagnostics.openDiagnostics(this.app);
      },
    });
    this.disposeSettings = settingsTab.dispose;
    this.addSettingTab(settingsTab.tab);

    this.registerView(CHAT_VIEW_TYPE, (leaf) => new ChatView(leaf, { store: chat.store }));
    this.registerView(SEARCH_VIEW_TYPE, (leaf) => new SearchView(leaf, { store: search.store }));
    this.registerView(
      STATUS_VIEW_TYPE,
      (leaf) =>
        new StatusView(leaf, {
          store: status.store,
          openDiagnostics: () => {
            diagnostics.openDiagnostics(this.app);
          },
        }),
    );

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

    registerCommands(this, {
      app: this.app,
      chatStore: chat.store,
      statusStore: status.store,
      openOnboarding: (app) => {
        onboarding.openOnboarding(app);
      },
      openDiagnostics: (app) => {
        diagnostics.openDiagnostics(app);
      },
      activateChat: activateChatView,
      activateSearch: activateSearchView,
      activateStatus: activateStatusView,
    });

    registerContextMenu(this, {
      askAboutNote: (path) => {
        chat.store.focusNote(path);
        void activateChatView(this.app);
      },
      searchInFolder: (path) => {
        void activateSearchView(this.app);
        void search.store.focusFolder(path);
      },
      reindexFile: (path) => {
        void indexing.reindexFile(path);
      },
    });

    this.app.workspace.onLayoutReady(() => {
      void onboarding.openOnboardingIfNeeded(this.app);
    });
  }

  override onunload(): void {
    this.disposeSettings?.();
    this.disposeSettings = null;
    this.disposeStatusBar?.();
    this.disposeStatusBar = null;
    this.disposeChat?.();
    this.disposeChat = null;
    this.disposeSearch?.();
    this.disposeSearch = null;
    this.disposeStatus?.();
    this.disposeStatus = null;
    this.disposeAutoIndexing?.();
    this.disposeAutoIndexing = null;
    this.disposeIndexing?.();
    this.disposeIndexing = null;
    this.disposeRuntimeLifecycle?.();
    this.disposeRuntimeLifecycle = null;
  }
}
