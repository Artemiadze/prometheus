import { Plugin } from "obsidian";

import { DedupNotifier } from "../adapters/inbound/notifier/DedupNotifier";
import { ObsidianNotifier } from "../adapters/inbound/notifier/ObsidianNotifier";
import { CompositeLogger, ConsoleLogger, RecentEventsBuffer } from "../adapters/outbound/logging";
import { ensureVaultId, ObsidianSettingsRepository } from "../adapters/outbound/settings";
import { SystemClock } from "../adapters/outbound/system/SystemClock";
import { createActivationGate, detachPluginLeaves } from "./pluginLifecycle";
import { registerPluginUi } from "./registerPluginUi";
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
 * Constructs the graph once; views receive stores only (PLG-77).
 * Continuous work (status poll, vault auto-index) waits for ActivationGate (PLG-78).
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

    // Activation gate is created after status + autoIndexing; chat/search get a late-bound hook.
    let activateFeatures: () => void = () => undefined;

    const search = wireSearch({
      app: this.app,
      settings,
      rag: runtime.rag,
      startRuntime: runtime.startRuntime,
      notifier,
      onActivated: () => {
        activateFeatures();
      },
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

    const activation = createActivationGate({
      statusStore: status.store,
      autoIndexing,
    });
    activateFeatures = activation.activate;

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
      onActivated: activation.activate,
    });

    const chat = wireChat({
      app: this.app,
      settings,
      rag: runtime.rag,
      startRuntime: runtime.startRuntime,
      notifier,
      vault: search.vault,
      resolveScope: createChatScopeResolver({ settings, vault: search.vault }),
      onActivated: activation.activate,
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
      onActivated: activation.activate,
    });
    this.disposeSettings = settingsTab.dispose;

    const ui = registerPluginUi({
      plugin: this,
      app: this.app,
      chatStore: chat.store,
      searchStore: search.store,
      statusStore: status.store,
      settingsTab: settingsTab.tab,
      openOnboarding: (app) => {
        onboarding.openOnboarding(app);
      },
      openDiagnostics: (app) => {
        diagnostics.openDiagnostics(app);
      },
      reindexFile: (path) => {
        void indexing.reindexFile(path);
      },
      onActivate: activation.activate,
    });
    this.disposeStatusBar = ui.disposeStatusBar;

    this.app.workspace.onLayoutReady(() => {
      void (async () => {
        await onboarding.openOnboardingIfNeeded(this.app);
        const current = await settings.get();
        if (current.runtimeAutostart) {
          void runtime.startRuntime.execute().then((result) => {
            if (result.kind === "ready") {
              activation.activate();
            }
          });
        }
      })();
    });
  }

  override onunload(): void {
    detachPluginLeaves(this.app);
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
