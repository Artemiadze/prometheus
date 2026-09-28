import { Modal, type App } from "obsidian";

import {
  ONBOARDING_STEP_TITLES,
  type OnboardingController,
  type OnboardingState,
  type OnboardingStepId,
} from "./OnboardingController";
import { renderIndexingProgress } from "../status/indexingProgress";

export type OnboardingModalDeps = {
  readonly controller: OnboardingController;
};

/**
 * First-run setup wizard (PLG-63). Network is only needed for runtime download.
 */
export class OnboardingModal extends Modal {
  private readonly controller: OnboardingController;
  private unsubscribe: (() => void) | null = null;
  private bodyEl: HTMLElement | null = null;

  constructor(app: App, deps: OnboardingModalDeps) {
    super(app);
    this.controller = deps.controller;
  }

  override onOpen(): void {
    this.titleEl.setText("Prometheus setup");
    this.contentEl.empty();
    this.contentEl.addClass("prometheus-onboarding");
    this.bodyEl = this.contentEl.createDiv({ cls: "prometheus-onboarding__body" });
    this.contentEl.createDiv({
      cls: "prometheus-onboarding__note",
      text: "Network is only needed for step 1 (runtime download). Everything else runs locally.",
    });

    this.unsubscribe = this.controller.subscribe((state) => {
      this.render(state);
    });

    void this.controller.runCurrentStep();
  }

  override onClose(): void {
    this.unsubscribe?.();
    this.unsubscribe = null;
    this.bodyEl = null;
    void this.controller.finish();
    this.controller.dispose();
    this.contentEl.empty();
  }

  private render(state: OnboardingState): void {
    const bodyEl = this.bodyEl;
    if (!bodyEl) {
      return;
    }
    bodyEl.empty();

    if (state.completed) {
      bodyEl.createDiv({
        cls: "prometheus-onboarding__done",
        text: "Setup complete. You can close this window.",
      });
      const close = bodyEl.createEl("button", {
        text: "Done",
        cls: "prometheus-onboarding__primary",
      });
      close.addEventListener("click", () => {
        this.close();
      });
      return;
    }

    for (const step of state.steps) {
      this.renderStep(bodyEl, step.id, step.status, step.message, state);
    }
  }

  private renderStep(
    parent: HTMLElement,
    id: OnboardingStepId,
    status: OnboardingState["steps"][number]["status"],
    message: string | null,
    state: OnboardingState,
  ): void {
    const card = parent.createDiv({
      cls: `prometheus-onboarding__step prometheus-onboarding__step--${status}`,
    });
    card.createDiv({
      cls: "prometheus-onboarding__step-title",
      text: ONBOARDING_STEP_TITLES[id],
    });
    card.createDiv({
      cls: "prometheus-onboarding__step-status",
      text: statusLabel(status),
    });
    if (message) {
      card.createDiv({ cls: "prometheus-onboarding__step-message", text: message });
    }

    if (id === "install" && state.installState) {
      const install = state.installState;
      const text =
        install.kind === "downloading"
          ? `Downloading… ${install.progressPercent}%`
          : install.kind === "verifying"
            ? "Verifying…"
            : install.kind;
      card.createDiv({ cls: "prometheus-onboarding__step-message", text });
    }

    if (id === "model" && state.currentStep === "model" && state.models.length > 0) {
      const list = card.createDiv({ cls: "prometheus-onboarding__models" });
      for (const model of state.models) {
        if (!model.installed) {
          continue;
        }
        const button = list.createEl("button", {
          text: model.name,
          cls: "prometheus-onboarding__model-btn",
        });
        button.addEventListener("click", () => {
          void this.controller.selectModel(model.name);
        });
      }
    }

    if (id === "index" && state.indexingProgress) {
      const progress = card.createDiv();
      renderIndexingProgress(progress, state.indexingProgress);
      const cancel = card.createEl("button", {
        text: "Cancel indexing",
        cls: "prometheus-onboarding__secondary",
      });
      cancel.addEventListener("click", () => {
        void this.controller.cancelIndexing();
      });
    }

    if (state.currentStep === id && (status === "error" || status === "pending")) {
      if (id === "model" && state.models.length > 0 && status === "pending") {
        return;
      }
      const retry = card.createEl("button", {
        text: status === "error" ? "Retry" : "Continue",
        cls: "prometheus-onboarding__primary",
      });
      retry.addEventListener("click", () => {
        void this.controller.runCurrentStep();
      });
    }
  }
}

function statusLabel(status: OnboardingState["steps"][number]["status"]): string {
  switch (status) {
    case "pending":
      return "Waiting";
    case "running":
      return "In progress…";
    case "success":
      return "Done";
    case "error":
      return "Needs attention";
    default: {
      const _exhaustive: never = status;
      return _exhaustive;
    }
  }
}
