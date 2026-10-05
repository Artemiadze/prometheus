import { Component, ItemView, MarkdownRenderer, type WorkspaceLeaf } from "obsidian";

import type { ChatMessage } from "../../../../domain/entities/ChatMessage";
import type { SourceReference } from "../../../../domain/entities/SourceReference";
import type { ChatStore, ChatViewState } from "../chat/ChatStore";
import { resolveComposerKey } from "../chat/composerKeys";
import { messageRenderKey, planMessageRender } from "../chat/planMessageRender";
import { sanitizeAssistantMarkdown } from "../chat/sanitizeAssistantMarkdown";
import { visibleSources } from "../chat/visibleSources";

export const CHAT_VIEW_TYPE = "prometheus-chat";

const INSUFFICIENT_HINT = "Try rephrasing the question or check the indexing status.";

export type ChatViewOptions = {
  readonly store: ChatStore;
  readonly onActivate?: () => void;
};

export class ChatView extends ItemView {
  private readonly store: ChatStore;
  private readonly onActivate: (() => void) | null;
  private unsubscribe: (() => void) | null = null;
  private messagesEl: HTMLElement | null = null;
  private textareaEl: HTMLTextAreaElement | null = null;
  private actionButtonEl: HTMLButtonElement | null = null;
  private errorEl: HTMLElement | null = null;
  private scopeBadgeEl: HTMLElement | null = null;
  private readonly messageComponents = new Map<string, Component>();
  private readonly messageRoots = new Map<string, HTMLElement>();
  private prevRenderKeys: string[] = [];
  private focusedScopeBadge = false;

  constructor(leaf: WorkspaceLeaf, options: ChatViewOptions) {
    super(leaf);
    this.store = options.store;
    this.onActivate = options.onActivate ?? null;
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

    const header = container.createDiv({ cls: "prometheus-chat-view__header" });
    header.createEl("h2", { text: "Chat", cls: "prometheus-chat-view__title" });
    const clearButton = header.createEl("button", {
      text: "Clear",
      cls: "prometheus-chat-view__clear",
    });
    clearButton.addEventListener("click", () => {
      this.store.clear();
    });

    this.errorEl = container.createDiv({ cls: "prometheus-chat-view__error" });
    this.messagesEl = container.createDiv({ cls: "prometheus-chat-view__messages" });

    this.scopeBadgeEl = container.createDiv({ cls: "prometheus-chat-view__scope-badge" });
    this.scopeBadgeEl.hide();

    const inputRow = container.createDiv({ cls: "prometheus-chat-view__input" });
    this.textareaEl = inputRow.createEl("textarea", {
      attr: { placeholder: "Ask your notes…", rows: "3" },
    });
    this.actionButtonEl = inputRow.createEl("button", {
      cls: "prometheus-chat-view__submit",
      text: "Send",
    });

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

    this.actionButtonEl.addEventListener("click", () => {
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
    for (const component of this.messageComponents.values()) {
      component.unload();
    }
    this.messageComponents.clear();
    this.messageRoots.clear();
    this.prevRenderKeys = [];
    this.contentEl.empty();
  }

  private async submitFromInput(): Promise<void> {
    const textarea = this.textareaEl;
    const status = this.store.getState().status;
    if (!textarea || status === "sending" || status === "streaming") {
      return;
    }
    const text = textarea.value;
    textarea.value = "";
    await this.store.send(text);
  }

  private render(state: ChatViewState): void {
    this.renderError(state);
    this.renderMessages(state);
    this.renderScopeBadge(state);
    this.renderComposer(state);
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
    const button = this.actionButtonEl;
    if (!textarea || !button) {
      return;
    }
    const busy = state.status === "sending" || state.status === "streaming";
    textarea.disabled = busy;
    button.toggleClass("mod-warning", busy);
    button.setText(busy ? "Cancel" : "Send");
  }

  private renderMessages(state: ChatViewState): void {
    const messagesEl = this.messagesEl;
    if (!messagesEl) {
      return;
    }
    const messages = state.session.messages;
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
        void this.renderMessageContent(message, root, key);
      } else if (root) {
        root.className = this.messageClass(message);
      }
    });

    keys.forEach((key, index) => {
      const root = this.messageRoots.get(key);
      if (!root) {
        return;
      }
      const current = messagesEl.children[index];
      if (current !== root) {
        messagesEl.insertBefore(root, current ?? null);
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
  ): Promise<void> {
    root.empty();
    const component = new Component();
    this.messageComponents.set(key, component);
    component.load();

    if (message.kind === "user") {
      root.createDiv({ cls: "prometheus-chat-message__label", text: "You" });
      root.createDiv({ cls: "prometheus-chat-message__body", text: message.text });
      return;
    }

    root.createDiv({ cls: "prometheus-chat-message__label", text: "Assistant" });
    const body = root.createDiv({ cls: "prometheus-chat-message__body" });

    if (message.state === "pending") {
      body.setText("Thinking…");
      return;
    }
    if (message.state === "streaming") {
      body.setText(message.text.length > 0 ? message.text : "Thinking…");
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
      return;
    }

    const markdown = sanitizeAssistantMarkdown(message.text);
    await MarkdownRenderer.render(this.app, markdown, body, "", component);

    const sources = visibleSources(message);
    if (sources.length > 0) {
      const sourcesBlock = root.createDiv({ cls: "prometheus-chat-message__sources" });
      sourcesBlock.createDiv({ cls: "prometheus-chat-message__sources-title", text: "Sources" });
      const list = sourcesBlock.createEl("ul", { cls: "prometheus-chat-message__sources-list" });
      for (const source of sources) {
        this.renderSourceItem(list, source);
      }
    }
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
