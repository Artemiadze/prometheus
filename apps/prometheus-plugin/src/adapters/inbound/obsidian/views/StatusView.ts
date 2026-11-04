import { ItemView, type WorkspaceLeaf } from "obsidian";

import type { StatusStore, StatusViewState } from "../status/StatusStore";
import { buildStatusRows, indexActionLabel, runtimeActionLabel } from "../status/statusCopy";
import { renderIndexingProgress } from "../status/indexingProgress";

export const STATUS_VIEW_TYPE = "prometheus-status";

export type StatusViewOptions = {
  readonly store: StatusStore;
  readonly openDiagnostics?: () => void;
  readonly onActivate?: () => void;
};

export class StatusView extends ItemView {
  private readonly store: StatusStore;
  private readonly openDiagnostics: (() => void) | null;
  private readonly onActivate: (() => void) | null;
  private unsubscribe: (() => void) | null = null;
  private panelEl: HTMLElement | null = null;
  private actionsEl: HTMLElement | null = null;
  private progressEl: HTMLElement | null = null;
  private errorEl: HTMLElement | null = null;
  constructor(leaf: WorkspaceLeaf, options: StatusViewOptions) {
    super(leaf);
    this.store = options.store;
    this.openDiagnostics = options.openDiagnostics ?? null;
    this.onActivate = options.onActivate ?? null;
  }

  override getViewType(): string {
    return STATUS_VIEW_TYPE;
  }

  override getDisplayText(): string {
    return "Prometheus Status";
  }

  override getIcon(): string {
    return "activity";
  }

  override async onOpen(): Promise<void> {
    this.onActivate?.();
    const container = this.contentEl;
    container.empty();
    container.addClass("prometheus-status-view");

    container.createEl("h2", { text: "Prometheus", cls: "prometheus-status-view__title" });
    this.errorEl = container.createDiv({ cls: "prometheus-status-view__error" });
    this.panelEl = container.createDiv({ cls: "prometheus-status-view__panel" });
    this.progressEl = container.createDiv({ cls: "prometheus-status-view__progress-wrap" });
    this.actionsEl = container.createDiv({ cls: "prometheus-status-view__actions" });

    this.unsubscribe = this.store.subscribe((state) => {
      this.render(state);
    });
  }

  override async onClose(): Promise<void> {
    this.unsubscribe?.();
    this.unsubscribe = null;
    this.panelEl = null;
    this.actionsEl = null;
    this.progressEl = null;
    this.errorEl = null;
    this.contentEl.empty();
  }

  private render(state: StatusViewState): void {
    this.renderError(state);
    this.renderRows(state);
    this.renderProgress(state);
    this.renderActions(state);
  }

  private renderError(state: StatusViewState): void {
    const errorEl = this.errorEl;
    if (!errorEl) {
      return;
    }
    if (state.actionError) {
      errorEl.setText(state.actionError);
      errorEl.show();
    } else {
      errorEl.setText("");
      errorEl.hide();
    }
  }

  private renderRows(state: StatusViewState): void {
    const panelEl = this.panelEl;
    if (!panelEl) {
      return;
    }
    panelEl.empty();
    if (!state.status) {
      panelEl.createDiv({
        cls: "prometheus-status-view__item",
        text: "Loading status…",
      });
      return;
    }
    const rows = buildStatusRows(state.status);
    for (const row of rows) {
      const item = panelEl.createDiv({
        cls: `prometheus-status-view__item prometheus-status-view__item--${row.tone}`,
      });
      item.createSpan({ cls: "prometheus-status-view__item-label", text: row.label });
      item.createSpan({ cls: "prometheus-status-view__item-value", text: row.value });
    }
  }

  private renderProgress(state: StatusViewState): void {
    const progressEl = this.progressEl;
    if (!progressEl) {
      return;
    }
    progressEl.empty();
    if (!state.indexingProgress) {
      progressEl.hide();
      return;
    }
    progressEl.show();
    renderIndexingProgress(progressEl, state.indexingProgress);
    const cancel = progressEl.createEl("button", {
      text: "Cancel indexing",
      cls: "prometheus-status-view__action",
    });
    cancel.addEventListener("click", () => {
      void this.store.cancelIndexing();
    });
  }

  private renderActions(state: StatusViewState): void {
    const actionsEl = this.actionsEl;
    if (!actionsEl) {
      return;
    }
    actionsEl.empty();
    const runtimeLabel = runtimeActionLabel(state.runtimeAction);
    if (runtimeLabel) {
      const button = actionsEl.createEl("button", {
        text: runtimeLabel,
        cls: "prometheus-status-view__action",
      });
      button.disabled = state.actionBusy;
      button.addEventListener("click", () => {
        if (state.runtimeAction === "download" || state.runtimeAction === "updateRuntime") {
          void this.store.installRuntime();
        } else if (state.runtimeAction === "restart") {
          void this.store.restartRuntime();
        }
      });
    }

    const indexLabel = indexActionLabel(state.indexAction);
    if (indexLabel && !state.indexingProgress) {
      const button = actionsEl.createEl("button", {
        text: indexLabel,
        cls: "prometheus-status-view__action",
      });
      button.disabled = state.actionBusy;
      button.addEventListener("click", () => {
        void this.store.reindex();
      });
    }

    if (this.openDiagnostics) {
      const diagnostics = actionsEl.createEl("button", {
        text: "Diagnostics",
        cls: "prometheus-status-view__action",
      });
      diagnostics.addEventListener("click", () => {
        this.openDiagnostics?.();
      });
    }
  }
}
