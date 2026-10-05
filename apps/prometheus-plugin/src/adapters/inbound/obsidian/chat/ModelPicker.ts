import { Menu, setIcon } from "obsidian";

import type { StatusStore } from "../status/StatusStore";

export type ModelPickerOptions = {
  readonly statusStore: StatusStore;
};

/** Composer pill that selects a local LLM via StatusStore. */
export class ModelPicker {
  private readonly statusStore: StatusStore;
  private rootEl: HTMLButtonElement | null = null;
  private labelEl: HTMLElement | null = null;
  private unsubscribe: (() => void) | null = null;

  constructor(options: ModelPickerOptions) {
    this.statusStore = options.statusStore;
  }

  mount(parent: HTMLElement): void {
    this.unsubscribe?.();
    const button = parent.createEl("button", {
      cls: "prometheus-chat-pill prometheus-chat-pill--model",
      attr: { type: "button" },
    });
    this.rootEl = button;
    this.labelEl = button.createSpan({ cls: "prometheus-chat-pill__label" });
    const chevron = button.createSpan({ cls: "prometheus-chat-pill__chevron" });
    setIcon(chevron, "chevron-down");

    button.addEventListener("click", (event) => {
      event.preventDefault();
      void this.openMenu(button);
    });

    this.unsubscribe = this.statusStore.subscribe((state) => {
      this.render(state);
    });
  }

  dispose(): void {
    this.unsubscribe?.();
    this.unsubscribe = null;
    this.rootEl?.remove();
    this.rootEl = null;
    this.labelEl = null;
  }

  private render(state: ReturnType<StatusStore["getState"]>): void {
    const root = this.rootEl;
    const label = this.labelEl;
    if (!root || !label) {
      return;
    }
    root.toggleClass("is-busy", state.actionBusy);
    root.disabled = state.actionBusy;

    const selected = state.status?.runtime.selectedModel ?? null;
    if (!selected) {
      label.setText("Select model");
      root.removeClass("prometheus-chat-pill--warn");
      return;
    }
    if (!selected.installed) {
      label.setText(`${selected.name} (not installed)`);
      root.addClass("prometheus-chat-pill--warn");
      return;
    }
    root.removeClass("prometheus-chat-pill--warn");
    const choice = state.models.find((model) => model.name === selected.name);
    const suffix = choice?.quantization ? ` · ${choice.quantization}` : "";
    label.setText(`${selected.name}${suffix}`);
  }

  private async openMenu(anchor: HTMLElement): Promise<void> {
    await this.statusStore.refreshModels();
    const state = this.statusStore.getState();
    const selectedName = state.status?.runtime.selectedModel?.name ?? null;
    const installed = state.models.filter((model) => model.installed);

    const menu = new Menu();
    if (installed.length === 0) {
      menu.addItem((item) => {
        item.setTitle("No local models found");
        item.setDisabled(true);
      });
    } else {
      for (const model of installed) {
        const name = model.name;
        menu.addItem((item) => {
          item.setTitle(name);
          if (selectedName === name) {
            item.setIcon("check");
          }
          item.onClick(() => {
            void this.statusStore.selectModel(name);
          });
        });
      }
    }
    const rect = anchor.getBoundingClientRect();
    menu.showAtPosition({ x: rect.left, y: rect.bottom, width: rect.width });
  }
}
