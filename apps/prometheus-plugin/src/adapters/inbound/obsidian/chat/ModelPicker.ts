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
  private activeMenu: Menu | null = null;
  private menuToken = 0;
  /** Prevents reopen when the same click both closes the menu and hits the trigger. */
  private suppressOpenUntilMs = 0;

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
      if (performance.now() < this.suppressOpenUntilMs) {
        return;
      }
      if (this.activeMenu !== null) {
        this.activeMenu.hide();
        return;
      }
      void this.openMenu(button);
    });

    this.unsubscribe = this.statusStore.subscribe((state) => {
      this.render(state);
    });
  }

  dispose(): void {
    this.menuToken += 1;
    this.activeMenu?.hide();
    this.activeMenu = null;
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
    const token = ++this.menuToken;
    await this.statusStore.refreshModels();
    if (token !== this.menuToken || this.rootEl !== anchor) {
      return;
    }

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
    menu.onHide(() => {
      if (this.activeMenu === menu) {
        this.activeMenu = null;
      }
      this.suppressOpenUntilMs = performance.now() + 200;
    });
    this.activeMenu = menu;
    const rect = anchor.getBoundingClientRect();
    menu.showAtPosition({ x: rect.left, y: rect.bottom, width: rect.width });
  }
}
