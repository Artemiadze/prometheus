import type { App, Plugin } from "obsidian";

import { registerCommands } from "../adapters/inbound/obsidian/commands/registerCommands";
import { registerContextMenu } from "../adapters/inbound/obsidian/commands/registerContextMenu";
import type { ChatStore } from "../adapters/inbound/obsidian/chat/ChatStore";
import type { SearchStore } from "../adapters/inbound/obsidian/search/SearchStore";
import type { StatusStore } from "../adapters/inbound/obsidian/status/StatusStore";
import { formatStatusBarLabel } from "../adapters/inbound/obsidian/status/formatStatusBarLabel";
import type { SettingsTab } from "../adapters/inbound/obsidian/SettingsTab";
import { activateChatView } from "../adapters/inbound/obsidian/views/activateChatView";
import { activateSearchView } from "../adapters/inbound/obsidian/views/activateSearchView";
import { activateStatusView } from "../adapters/inbound/obsidian/views/activateStatusView";
import { CHAT_VIEW_TYPE, ChatView } from "../adapters/inbound/obsidian/views/ChatView";
import { SEARCH_VIEW_TYPE, SearchView } from "../adapters/inbound/obsidian/views/SearchView";
import { STATUS_VIEW_TYPE, StatusView } from "../adapters/inbound/obsidian/views/StatusView";
import type { NotePath } from "../domain/value-objects/NotePath";

export type RegisterPluginUiDeps = {
  readonly plugin: Plugin;
  readonly app: App;
  readonly chatStore: ChatStore;
  readonly searchStore: SearchStore;
  readonly statusStore: StatusStore;
  readonly settingsTab: SettingsTab;
  readonly openOnboarding: (app: App) => void;
  readonly openDiagnostics: (app: App) => void;
  readonly reindexFile: (path: NotePath) => void;
  readonly onActivate: () => void;
};

export type RegisteredPluginUi = {
  readonly disposeStatusBar: () => void;
};

/**
 * Registers Obsidian views, ribbons, status bar, commands, and context menus.
 * Creates no outbound adapters — composition root must wire those first.
 */
export function registerPluginUi(deps: RegisterPluginUiDeps): RegisteredPluginUi {
  const { plugin, app } = deps;

  plugin.addSettingTab(deps.settingsTab);

  plugin.registerView(
    CHAT_VIEW_TYPE,
    (leaf) => new ChatView(leaf, { store: deps.chatStore, onActivate: deps.onActivate }),
  );
  plugin.registerView(
    SEARCH_VIEW_TYPE,
    (leaf) => new SearchView(leaf, { store: deps.searchStore, onActivate: deps.onActivate }),
  );
  plugin.registerView(
    STATUS_VIEW_TYPE,
    (leaf) =>
      new StatusView(leaf, {
        store: deps.statusStore,
        openDiagnostics: () => {
          deps.openDiagnostics(app);
        },
        onActivate: deps.onActivate,
      }),
  );

  plugin.addRibbonIcon("message-square", "Open Prometheus chat", () => {
    deps.onActivate();
    void activateChatView(app);
  });
  plugin.addRibbonIcon("activity", "Open Prometheus status", () => {
    deps.onActivate();
    void activateStatusView(app);
  });

  const syncActiveUiViews = (): void => {
    let count = 0;
    app.workspace.iterateAllLeaves((leaf) => {
      const type = leaf.view.getViewType();
      if (type === CHAT_VIEW_TYPE || type === SEARCH_VIEW_TYPE || type === STATUS_VIEW_TYPE) {
        count += 1;
      }
    });
    deps.statusStore.setActiveUiViews(count);
  };
  syncActiveUiViews();
  plugin.registerEvent(app.workspace.on("layout-change", syncActiveUiViews));

  const statusBarItem = plugin.addStatusBarItem();
  statusBarItem.addClass("prometheus-statusbar-item");
  statusBarItem.setText("Prometheus");
  statusBarItem.addEventListener("click", () => {
    deps.onActivate();
    void activateStatusView(app);
  });
  const disposeStatusBar = deps.statusStore.subscribe((state) => {
    if (state.status === null && !deps.statusStore.isPolling()) {
      statusBarItem.setText("Prometheus");
      statusBarItem.removeClass("prometheus-statusbar-item--ready");
      statusBarItem.removeClass("prometheus-statusbar-item--indexing");
      statusBarItem.removeClass("prometheus-statusbar-item--error");
      statusBarItem.removeClass("prometheus-statusbar-item--busy");
      return;
    }
    const label = formatStatusBarLabel(state.status, state.runtimeAction, state.indexAction);
    statusBarItem.setText(label.text);
    statusBarItem.toggleClass("prometheus-statusbar-item--ready", label.kind === "ready");
    statusBarItem.toggleClass("prometheus-statusbar-item--indexing", label.kind === "indexing");
    statusBarItem.toggleClass("prometheus-statusbar-item--error", label.kind === "error");
    statusBarItem.toggleClass("prometheus-statusbar-item--busy", label.kind === "busy");
  });

  registerCommands(plugin, {
    app,
    chatStore: deps.chatStore,
    statusStore: deps.statusStore,
    openOnboarding: (targetApp) => {
      deps.onActivate();
      deps.openOnboarding(targetApp);
    },
    openDiagnostics: (targetApp) => {
      deps.onActivate();
      deps.openDiagnostics(targetApp);
    },
    activateChat: (targetApp) => {
      deps.onActivate();
      return activateChatView(targetApp);
    },
    activateSearch: (targetApp) => {
      deps.onActivate();
      return activateSearchView(targetApp);
    },
    activateStatus: (targetApp) => {
      deps.onActivate();
      return activateStatusView(targetApp);
    },
  });

  registerContextMenu(plugin, {
    askAboutNote: (path) => {
      deps.onActivate();
      deps.chatStore.focusNote(path);
      void activateChatView(app);
    },
    searchInFolder: (path) => {
      deps.onActivate();
      void activateSearchView(app);
      void deps.searchStore.focusFolder(path);
    },
    reindexFile: (path) => {
      deps.onActivate();
      deps.reindexFile(path);
    },
  });

  return { disposeStatusBar };
}
