import { Modal, type App } from "obsidian";

import type { Notifier } from "../../../../application/ports/Notifier";
import { buildDiagnosticsReport } from "../../../../application/services/buildDiagnosticsReport";
import type { CollectDiagnostics } from "../../../../application/use-cases/CollectDiagnostics";

export type DiagnosticsModalDeps = {
  readonly collect: CollectDiagnostics;
  readonly notifier: Pick<Notifier, "info" | "error">;
};

/**
 * Copyable diagnostics report modal (PLG-75).
 */
export class DiagnosticsModal extends Modal {
  private readonly collect: CollectDiagnostics;
  private readonly notifier: Pick<Notifier, "info" | "error">;
  private bodyEl: HTMLElement | null = null;
  private reportText = "";
  private busy = false;

  constructor(app: App, deps: DiagnosticsModalDeps) {
    super(app);
    this.collect = deps.collect;
    this.notifier = deps.notifier;
  }

  override onOpen(): void {
    this.titleEl.setText("Prometheus Diagnostics");
    this.contentEl.empty();
    this.contentEl.addClass("prometheus-diagnostics");

    const actions = this.contentEl.createDiv({ cls: "prometheus-diagnostics__actions" });
    const refresh = actions.createEl("button", {
      text: "Refresh",
      cls: "prometheus-diagnostics__button",
    });
    refresh.addEventListener("click", () => {
      void this.refresh();
    });
    const copy = actions.createEl("button", {
      text: "Copy report",
      cls: "prometheus-diagnostics__button mod-cta",
    });
    copy.addEventListener("click", () => {
      void this.copyReport();
    });

    this.bodyEl = this.contentEl.createEl("pre", { cls: "prometheus-diagnostics__report" });
    void this.refresh();
  }

  override onClose(): void {
    this.bodyEl = null;
    this.contentEl.empty();
  }

  private async refresh(): Promise<void> {
    if (this.busy || !this.bodyEl) {
      return;
    }
    this.busy = true;
    this.bodyEl.setText("Collecting…");
    try {
      const snapshot = await this.collect.execute();
      this.reportText = buildDiagnosticsReport(snapshot);
      this.bodyEl.setText(this.reportText);
    } catch {
      this.reportText = "";
      this.bodyEl.setText("Unable to collect diagnostics.");
      this.notifier.error("Unable to collect diagnostics. Try again.");
    } finally {
      this.busy = false;
    }
  }

  private async copyReport(): Promise<void> {
    if (!this.reportText) {
      await this.refresh();
    }
    if (!this.reportText) {
      return;
    }
    try {
      await navigator.clipboard.writeText(this.reportText);
      this.notifier.info("Diagnostics copied.");
    } catch {
      this.notifier.error("Unable to copy diagnostics to the clipboard.");
    }
  }
}
