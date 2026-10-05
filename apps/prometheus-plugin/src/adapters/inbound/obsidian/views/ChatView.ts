import { Component, ItemView, MarkdownRenderer, Menu, setIcon, type WorkspaceLeaf } from "obsidian";

import type { ChatMessage } from "../../../../domain/entities/ChatMessage";
import type { SourceReference } from "../../../../domain/entities/SourceReference";
import type { ChatScopeMode, ChatStore, ChatViewState } from "../chat/ChatStore";
import { resolveComposerKey } from "../chat/composerKeys";
import { formatDuration } from "../chat/formatDuration";
import { ModelPicker } from "../chat/ModelPicker";
import { messageRenderKey, planMessageRender } from "../chat/planMessageRender";
import { sanitizeAssistantMarkdown } from "../chat/sanitizeAssistantMarkdown";
import { visibleSources } from "../chat/visibleSources";
import type { StatusStore } from "../status/StatusStore";

export const CHAT_VIEW_TYPE = "prometheus-chat";

const INSUFFICIENT_HINT = "Try rephrasing the question or check the indexing status.";
const EMPTY_HINT = "Ask a question about your notes";

export type ChatViewOptions = {
  readonly store: ChatStore;
  readonly statusStore: StatusStore;
  readonly onActivate?: () => void;
};

const SCOPE_LABELS: Record<ChatScopeMode, string> = {
  auto: "Auto",
  entire_vault: "Vault",
  current_note: "Current note",
  current_folder: "Current folder",
};

export class ChatView extends ItemView {
  private readonly store: ChatStore;
  private readonly onActivate: (() => void) | null;
  private unsubscribe: (() => void) | null = null;
  private tabsEl: HTMLElement | null = null;
  private messagesEl: HTMLElement | null = null;
  private emptyHintEl: HTMLElement | null = null;
  private textareaEl: HTMLTextAreaElement | null = null;
  private sendButtonEl: HTMLButtonElement | null = null;
  private errorEl: HTMLElement | null = null;
  private scopeBadgeEl: HTMLElement | null = null;
  private scopePillEl: HTMLButtonElement | null = null;
  private modelPicker: ModelPicker | null = null;
  private readonly messageComponents = new Map<string, Component>();
  private readonly messageRoots = new Map<string, HTMLElement>();
  private prevRenderKeys: string[] = [];
  private prevActiveTabId: string | null = null;
  private focusedScopeBadge = false;

  constructor(leaf: WorkspaceLeaf, options: ChatViewOptions) {
    super(leaf);
    this.store = options.store;
    this.onActivate = options.onActivate ?? null;
    this.modelPicker = new ModelPicker({ statusStore: options.statusStore });
  }

  override getViewType(): string {
    return CHAT_VIEW_TYPE;
  }

  override getDisplayText(): string {
    return "Prometheus Chat";
  }

  override getIcon(): string {
    return "message-square";
  }

  override async onOpen(): Promise<void> {
    this.onActivate?.();
    const container = this.contentEl;
    container.empty();
    container.addClass("prometheus-chat-view");

    this.tabsEl = container.createDiv({ cls: "prometheus-chat-tabs" });

    this.errorEl = container.createDiv({ cls: "prometheus-chat-view__error" });
    this.messagesEl = container.createDiv({ cls: "prometheus-chat-view__messages" });
    this.emptyHintEl = this.messagesEl.createDiv({
      cls: "prometheus-chat-view__empty-hint",
      text: EMPTY_HINT,
    });

    this.scopeBadgeEl = container.createDiv({ cls: "prometheus-chat-view__scope-badge" });
    this.scopeBadgeEl.hide();

    const composer = container.createDiv({ cls: "prometheus-chat-composer" });
    this.textareaEl = composer.createEl("textarea", {
      cls: "prometheus-chat-composer__input",
      attr: {
        placeholder: "Ask anything · + to add note context",
        rows: "1",
      },
    });
    const toolbar = composer.createDiv({ cls: "prometheus-chat-composer__toolbar" });
    const addContextBtn = toolbar.createEl("button", {
      cls: "prometheus-chat-composer__icon-btn",
      attr: { type: "button", "aria-label": "Add current note as context" },
    });
    setIcon(addContextBtn, "plus");
    addContextBtn.addEventListener("click", () => {
      void this.addCurrentNoteContext();
    });

    const pickerHost = toolbar.createDiv({ cls: "prometheus-chat-composer__picker-host" });
    this.modelPicker?.mount(pickerHost);

    toolbar.createDiv({ cls: "prometheus-chat-composer__spacer" });

    this.scopePillEl = toolbar.createEl("button", {
      cls: "prometheus-chat-pill prometheus-chat-pill--scope",
      attr: { type: "button" },
    });
    this.scopePillEl.createSpan({ cls: "prometheus-chat-pill__label" });
    const scopeChevron = this.scopePillEl.createSpan({ cls: "prometheus-chat-pill__chevron" });
    setIcon(scopeChevron, "chevron-down");
    this.scopePillEl.addEventListener("click", (event) => {
      event.preventDefault();
      this.openScopeMenu(this.scopePillEl!);
    });

    this.sendButtonEl = toolbar.createEl("button", {
      cls: "prometheus-chat-composer__send",
      attr: { type: "button", "aria-label": "Send" },
    });
    setIcon(this.sendButtonEl, "arrow-up");

    this.textareaEl.addEventListener("keydown", (event) => {
      const action = resolveComposerKey({
        key: event.key,
        shiftKey: event.shiftKey,
        isComposing: event.isComposing,
      });
      if (action === "send") {
        event.preventDefault();
        void this.submitFromInput();
      }
    });

    this.textareaEl.addEventListener("input", () => {
      this.autoGrowTextarea();
    });

    this.sendButtonEl.addEventListener("click", () => {
      const status = this.store.getState().status;
      if (status === "sending" || status === "streaming") {
        this.store.cancel();
        return;
      }
      void this.submitFromInput();
    });

    this.unsubscribe = this.store.subscribe((state) => {
      this.render(state);
    });
  }

  override async onClose(): Promise<void> {
    this.unsubscribe?.();
    this.unsubscribe = null;
    this.modelPicker?.dispose();
    this.modelPicker = null;
    for (const component of this.messageComponents.values()) {
      component.unload();
    }
    this.messageComponents.clear();
    this.messageRoots.clear();
    this.prevRenderKeys = [];
    this.prevActiveTabId = null;
    this.contentEl.empty();
  }

  private async addCurrentNoteContext(): Promise<void> {
    const file = this.app.workspace.getActiveFile();
    if (!file) {
      return;
    }
    const { NotePath } = await import("../../../../domain/value-objects/NotePath");
    this.store.focusNote(NotePath.create(file.path));
  }

  private openScopeMenu(anchor: HTMLElement): void {
    const state = this.store.getState();
    const menu = new Menu();
    const modes: ChatScopeMode[] = ["auto", "entire_vault", "current_note", "current_folder"];
    for (const mode of modes) {
      menu.addItem((item) => {
        item.setTitle(SCOPE_LABELS[mode]);
        if (state.scopeMode === mode) {
          item.setIcon("check");
        }
        item.onClick(() => {
          this.store.setScopeMode(mode);
        });
      });
    }
    const rect = anchor.getBoundingClientRect();
    menu.showAtPosition({ x: rect.left, y: rect.bottom, width: rect.width });
  }

  private autoGrowTextarea(): void {
    const textarea = this.textareaEl;
    if (!textarea) {
      return;
    }
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  }

  private async submitFromInput(): Promise<void> {
    const textarea = this.textareaEl;
    const status = this.store.getState().status;
    if (!textarea || status === "sending" || status === "streaming") {
      return;
    }
    const text = textarea.value;
    textarea.value = "";
    this.autoGrowTextarea();
    await this.store.send(text);
  }

  private render(state: ChatViewState): void {
    this.renderTabs(state);
    this.renderError(state);
    if (this.prevActiveTabId !== null && this.prevActiveTabId !== state.activeTabId) {
      this.resetMessageDom();
    }
    this.prevActiveTabId = state.activeTabId;
    this.renderMessages(state);
    this.renderScopeBadge(state);
    this.renderComposer(state);
  }

  private resetMessageDom(): void {
    for (const component of this.messageComponents.values()) {
      component.unload();
    }
    this.messageComponents.clear();
    this.messageRoots.clear();
    this.prevRenderKeys = [];
    this.messagesEl?.empty();
    if (this.messagesEl) {
      this.emptyHintEl = this.messagesEl.createDiv({
        cls: "prometheus-chat-view__empty-hint",
        text: EMPTY_HINT,
      });
    }
  }

  private renderTabs(state: ChatViewState): void {
    const tabsEl = this.tabsEl;
    if (!tabsEl) {
      return;
    }
    tabsEl.empty();
    for (const tab of state.tabs) {
      const tabEl = tabsEl.createDiv({
        cls: "prometheus-chat-tabs__tab",
      });
      tabEl.toggleClass("is-active", tab.id === state.activeTabId);
      tabEl.toggleClass("is-busy", tab.busy);
      const titleBtn = tabEl.createEl("button", {
        cls: "prometheus-chat-tabs__title",
        text: tab.title,
        attr: { type: "button" },
      });
      titleBtn.addEventListener("click", () => {
        this.store.switchTab(tab.id);
      });
      const closeBtn = tabEl.createEl("button", {
        cls: "prometheus-chat-tabs__close",
        attr: { type: "button", "aria-label": "Close chat" },
      });
      setIcon(closeBtn, "x");
      closeBtn.addEventListener("click", (event) => {
        event.stopPropagation();
        this.store.closeTab(tab.id);
      });
    }
    const newTabBtn = tabsEl.createEl("button", {
      cls: "prometheus-chat-tabs__new",
      attr: { type: "button", "aria-label": "New chat" },
    });
    setIcon(newTabBtn, "plus");
    newTabBtn.addEventListener("click", () => {
      this.store.newTab();
    });
  }

  private renderScopeBadge(state: ChatViewState): void {
    const badge = this.scopeBadgeEl;
    if (!badge) {
      return;
    }
    if (!state.scopeOverrideLabel) {
      badge.empty();
      badge.hide();
      this.focusedScopeBadge = false;
      return;
    }
    badge.empty();
    badge.show();
    badge.createSpan({
      cls: "prometheus-chat-view__scope-badge-text",
      text: `Asking about: ${state.scopeOverrideLabel}`,
    });
    const clearButton = badge.createEl("button", {
      cls: "prometheus-chat-view__scope-badge-clear",
      text: "×",
      attr: { "aria-label": "Clear note scope" },
    });
    clearButton.addEventListener("click", () => {
      this.store.clearScopeOverride();
    });
    if (!this.focusedScopeBadge && this.textareaEl) {
      this.focusedScopeBadge = true;
      this.textareaEl.focus();
    }
  }

  private renderError(state: ChatViewState): void {
    const errorEl = this.errorEl;
    if (!errorEl) {
      return;
    }
    if (state.errorMessage) {
      errorEl.setText(state.errorMessage);
      errorEl.show();
    } else {
      errorEl.setText("");
      errorEl.hide();
    }
  }

  private renderComposer(state: ChatViewState): void {
    const textarea = this.textareaEl;
    const button = this.sendButtonEl;
    const scopePill = this.scopePillEl;
    if (!textarea || !button) {
      return;
    }
    const busy = state.status === "sending" || state.status === "streaming";
    textarea.disabled = busy;
    button.toggleClass("is-busy", busy);
    button.empty();
    setIcon(button, busy ? "square" : "arrow-up");
    button.setAttr("aria-label", busy ? "Stop" : "Send");

    if (scopePill) {
      const label = scopePill.querySelector(".prometheus-chat-pill__label");
      label?.setText(SCOPE_LABELS[state.scopeMode]);
    }
  }

  private renderMessages(state: ChatViewState): void {
    const messagesEl = this.messagesEl;
    const emptyHint = this.emptyHintEl;
    if (!messagesEl) {
      return;
    }
    const messages = state.session.messages;
    emptyHint?.toggleClass("is-hidden", messages.length > 0);

    const keys = messages.map(messageRenderKey);
    const changedKeys = new Set(planMessageRender(this.prevRenderKeys, messages));

    for (const [key, root] of this.messageRoots.entries()) {
      if (!keys.includes(key)) {
        this.messageComponents.get(key)?.unload();
        this.messageComponents.delete(key);
        root.remove();
        this.messageRoots.delete(key);
      }
    }

    messages.forEach((message, index) => {
      const key = keys[index];
      if (!key) {
        return;
      }
      let root = this.messageRoots.get(key);
      if (!root || changedKeys.has(key)) {
        if (root) {
          this.messageComponents.get(key)?.unload();
          this.messageComponents.delete(key);
          root.remove();
        }
        root = messagesEl.createDiv({ cls: this.messageClass(message) });
        this.messageRoots.set(key, root);
        void this.renderMessageContent(message, root, key, state);
      } else if (root) {
        root.className = this.messageClass(message);
      }
    });

    const hintOffset = emptyHint ? 1 : 0;
    keys.forEach((key, index) => {
      const root = this.messageRoots.get(key);
      if (!root) {
        return;
      }
      const targetIndex = index + hintOffset;
      const currentAtIndex = messagesEl.children[targetIndex];
      if (currentAtIndex !== root) {
        messagesEl.insertBefore(root, currentAtIndex ?? null);
      }
    });

    this.prevRenderKeys = keys;
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  private messageClass(message: ChatMessage): string {
    const classes = ["prometheus-chat-message", `prometheus-chat-message--${message.kind}`];
    classes.push(`prometheus-chat-message--${message.state}`);
    if (message.kind === "assistant" && message.insufficientContext) {
      classes.push("prometheus-chat-message--insufficient");
    }
    return classes.join(" ");
  }

  private async renderMessageContent(
    message: ChatMessage,
    root: HTMLElement,
    key: string,
    state: ChatViewState,
  ): Promise<void> {
    root.empty();
    const component = new Component();
    this.messageComponents.set(key, component);
    component.load();

    if (message.kind === "user") {
      root.createDiv({ cls: "prometheus-chat-message__body", text: message.text });
      return;
    }

    const body = root.createDiv({ cls: "prometheus-chat-message__body" });

    if (message.state === "pending" || message.state === "streaming") {
      const thinking = body.createDiv({ cls: "prometheus-chat-message__thinking" });
      thinking.createSpan({ text: message.text.length > 0 ? message.text : "Thinking…" });
      return;
    }
    if (message.state === "cancelled") {
      body.setText("Cancelled.");
      return;
    }

    if (message.insufficientContext) {
      body.createDiv({
        cls: "prometheus-chat-message__insufficient-text",
        text: message.text || "Not enough information was found in your notes to answer.",
      });
      body.createDiv({
        cls: "prometheus-chat-message__insufficient-hint",
        text: INSUFFICIENT_HINT,
      });
      this.renderActivity(root, message, state);
      this.renderFooter(root, message, state);
      return;
    }

    const markdown = sanitizeAssistantMarkdown(message.text);
    await MarkdownRenderer.render(this.app, markdown, body, "", component);

    this.renderActivity(root, message, state);
    this.renderFooter(root, message, state);
  }

  private renderActivity(root: HTMLElement, message: ChatMessage, state: ChatViewState): void {
    if (message.kind !== "assistant" || message.state !== "complete") {
      return;
    }
    const sources = visibleSources(message);
    const durationMs = state.durationsMs[message.id];
    const durationPart = durationMs !== undefined ? ` · ${formatDuration(durationMs)}` : "";

    const details = root.createEl("details", { cls: "prometheus-chat-message__activity" });
    const summary = details.createEl("summary", {
      cls: "prometheus-chat-message__activity-summary",
    });
    const icon = summary.createSpan({ cls: "prometheus-chat-message__activity-icon" });
    setIcon(icon, "book-open");
    if (message.insufficientContext || sources.length === 0) {
      summary.createSpan({
        text: `No relevant notes found${durationPart}`,
      });
    } else {
      summary.createSpan({
        text: `Searched notes · ${sources.length} source${sources.length === 1 ? "" : "s"}${durationPart}`,
      });
    }
    if (sources.length > 0) {
      const list = details.createEl("ul", { cls: "prometheus-chat-message__sources-list" });
      for (const source of sources) {
        this.renderSourceItem(list, source);
      }
    }
  }

  private renderFooter(root: HTMLElement, message: ChatMessage, state: ChatViewState): void {
    if (message.kind !== "assistant" || message.state !== "complete") {
      return;
    }
    const durationMs = state.durationsMs[message.id];
    if (durationMs === undefined) {
      return;
    }
    const footer = root.createDiv({ cls: "prometheus-chat-message__footer" });
    const icon = footer.createSpan({ cls: "prometheus-chat-message__footer-icon" });
    setIcon(icon, "loader");
    footer.createSpan({
      cls: "prometheus-chat-message__footer-text",
      text: `Worked for ${formatDuration(durationMs)}`,
    });
    const copyBtn = footer.createEl("button", {
      cls: "prometheus-chat-message__copy",
      attr: { type: "button", "aria-label": "Copy response" },
    });
    setIcon(copyBtn, "copy");
    copyBtn.addEventListener("click", () => {
      void navigator.clipboard.writeText(message.text);
    });
  }

  private renderSourceItem(list: HTMLElement, source: SourceReference): void {
    const item = list.createEl("li", { cls: "prometheus-chat-message__source-item" });
    const button = item.createEl("button", {
      cls: "prometheus-chat-message__source-link",
      text: source.displayName,
    });
    button.addEventListener("click", () => {
      void this.store.openSource(source);
    });
  }
}
