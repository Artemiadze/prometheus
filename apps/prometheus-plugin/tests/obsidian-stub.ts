/**
 * Runtime stub for the types-only `obsidian` npm package so Vitest can load
 * value imports (TFile, Plugin, createDiv, …) used by adapter unit tests.
 */

export class TAbstractFile {
  path = "";
  name = "";
  parent: TFolder | null = null;
}

export class TFile extends TAbstractFile {
  extension = "";
  basename = "";
  stat = { ctime: 0, mtime: 0, size: 0 };
}

export class TFolder extends TAbstractFile {
  children: TAbstractFile[] = [];
}

export class Plugin {
  app: unknown;
  manifest: unknown;
  async loadData(): Promise<unknown> {
    return {};
  }
  async saveData(_data: unknown): Promise<void> {}
  addCommand(_command: unknown): void {}
  addSettingTab(_tab: unknown): void {}
  registerView(_type: string, _creator: unknown): void {}
  registerEvent(_event: unknown): void {}
}

export class ItemView {
  app: unknown;
  leaf: unknown;
  containerEl: HTMLElement = document.createElement("div");
  constructor(leaf: unknown) {
    this.leaf = leaf;
  }
}

export class Component {
  register(_cb: () => void): void {}
  unload(): void {}
}

export class Modal {
  app: unknown;
  contentEl: HTMLElement = document.createElement("div");
  titleEl: HTMLElement = document.createElement("div");
  constructor(app: unknown) {
    this.app = app;
  }
  open(): void {}
  close(): void {}
}

export class Menu {
  addItem(
    _cb: (item: { setTitle: (t: string) => unknown; onClick: (cb: () => void) => unknown }) => void,
  ): this {
    return this;
  }
  showAtMouseEvent(_event: MouseEvent): void {}
}

export class Notice {
  constructor(_message: string) {}
}

export class PluginSettingTab {
  app: unknown;
  plugin: unknown;
  containerEl: HTMLElement = document.createElement("div");
  constructor(app: unknown, plugin: unknown) {
    this.app = app;
    this.plugin = plugin;
  }
  display(): void {}
  hide(): void {}
  update(): void {}
}

export class Setting {
  settingEl: HTMLElement = document.createElement("div");
  descEl: HTMLElement = document.createElement("div");
  constructor(_containerEl: HTMLElement) {}
  setName(_name: string): this {
    return this;
  }
  setDesc(desc: string): this {
    this.descEl.textContent = desc;
    return this;
  }
  setHeading(): this {
    return this;
  }
  addToggle(_cb: (toggle: unknown) => void): this {
    return this;
  }
  addText(_cb: (text: unknown) => void): this {
    return this;
  }
  addTextArea(_cb: (area: unknown) => void): this {
    return this;
  }
  addDropdown(_cb: (dropdown: unknown) => void): this {
    return this;
  }
  addButton(_cb: (button: unknown) => void): this {
    return this;
  }
}

export class MarkdownRenderer {
  static async render(): Promise<void> {}
}

export function setIcon(_el: HTMLElement, _icon: string): void {}

export function createDiv(
  o?: { cls?: string; text?: string } | string,
  callback?: (el: HTMLDivElement) => void,
): HTMLDivElement {
  const el = document.createElement("div");
  if (typeof o === "string") {
    el.className = o;
  } else if (o?.cls) {
    el.className = o.cls;
  }
  if (typeof o === "object" && o?.text) {
    el.textContent = o.text;
  }
  callback?.(el);
  return el;
}

export function createEl(
  tag: string,
  o?: { cls?: string; text?: string },
  callback?: (el: HTMLElement) => void,
): HTMLElement {
  const el = document.createElement(tag);
  if (o?.cls) {
    el.className = o.cls;
  }
  if (o?.text) {
    el.textContent = o.text;
  }
  callback?.(el);
  return el;
}
