export type ActivationGateDeps = {
  readonly statusStore: { startPolling(): void };
  readonly autoIndexing: { applySettingsEnabled(): void | Promise<void> };
};

export type ActivationGate = {
  readonly activate: () => void;
  readonly isActivated: () => boolean;
};

/**
 * Idempotent gate: first “use” of the plugin starts status polling and vault auto-index.
 */
export function createActivationGate(deps: ActivationGateDeps): ActivationGate {
  let activated = false;
  return {
    activate: () => {
      if (activated) {
        return;
      }
      activated = true;
      deps.statusStore.startPolling();
      void deps.autoIndexing.applySettingsEnabled();
    },
    isActivated: () => activated,
  };
}

/** Keep in sync with ChatView / SearchView / StatusView VIEW_TYPE exports. */
export const PLUGIN_VIEW_TYPES = [
  "prometheus-chat",
  "prometheus-search",
  "prometheus-status",
] as const;

export type DetachLeavesApp = {
  readonly workspace: {
    detachLeavesOfType(type: string): void;
  };
};

/**
 * Detach Prometheus leaves so disposed stores are not left bound to workspace views.
 */
export function detachPluginLeaves(app: DetachLeavesApp): void {
  for (const type of PLUGIN_VIEW_TYPES) {
    app.workspace.detachLeavesOfType(type);
  }
}
