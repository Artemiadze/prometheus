import type { AskQuestion } from "../../../../application/use-cases/AskQuestion";
import { MIN_QUERY_LENGTH } from "../../../../application/use-cases/SearchNotes";
import { ChatSession } from "../../../../domain/entities/ChatSession";
import { ChatMessage as ChatMessageEntity } from "../../../../domain/entities/ChatMessage";
import { isAbortError } from "../../../../domain/errors";
import type { SourceReference } from "../../../../domain/entities/SourceReference";
import type { NotePath } from "../../../../domain/value-objects/NotePath";
import { SearchScope } from "../../../../domain/value-objects/SearchScope";
import { presentError } from "../errors/presentError";

export type ChatStatus = "idle" | "sending" | "streaming" | "error";

export type ChatScopeMode = "auto" | "entire_vault" | "current_note" | "current_folder";

export type ChatTabSummary = {
  readonly id: string;
  readonly title: string;
  readonly busy: boolean;
};

export type ChatViewState = {
  readonly status: ChatStatus;
  readonly session: ChatSession;
  readonly errorMessage: string | null;
  readonly scopeOverrideLabel: string | null;
  readonly tabs: readonly ChatTabSummary[];
  readonly activeTabId: string;
  readonly scopeMode: ChatScopeMode;
  readonly durationsMs: Readonly<Record<string, number>>;
};

export type ChatRuntimeReadiness =
  { readonly ok: true } | { readonly ok: false; readonly message: string };

export type ChatStoreDeps = {
  readonly askQuestion: Pick<AskQuestion, "execute">;
  readonly ensureRuntime: (signal: AbortSignal) => Promise<ChatRuntimeReadiness>;
  readonly openSource: (source: SourceReference) => Promise<void>;
  readonly resolveScope?: ((mode: ChatScopeMode) => Promise<SearchScope>) | undefined;
  readonly newSessionId?: (() => string) | undefined;
  readonly now?: () => number;
};

type ScopeOverride = {
  readonly scope: SearchScope;
  readonly label: string;
};

type ChatTab = {
  readonly id: string;
  title: string;
  session: ChatSession;
  status: ChatStatus;
  errorMessage: string | null;
  activeRequest: AbortController | null;
  durationsMs: Map<string, number>;
  scopeOverride: ScopeOverride | null;
  /** Wall-clock start of the in-flight send, for duration on the assistant message. */
  sendStartedAtMs: number | null;
  pendingAssistantMessageId: string | null;
};

type Listener = (state: ChatViewState) => void;

const DEFAULT_TAB_TITLE = "New chat";
const TAB_TITLE_MAX = 48;

export class ChatStore {
  private tabs: ChatTab[] = [];
  private activeTabId: string;
  private scopeMode: ChatScopeMode = "auto";
  private readonly listeners = new Set<Listener>();
  private disposed = false;
  private readonly now: () => number;

  constructor(private readonly deps: ChatStoreDeps) {
    this.now = deps.now ?? (() => Date.now());
    const first = this.createEmptyTab();
    this.tabs = [first];
    this.activeTabId = first.id;
  }

  getState(): ChatViewState {
    const active = this.requireActiveTab();
    const durationsMs: Record<string, number> = {};
    for (const [id, ms] of active.durationsMs.entries()) {
      durationsMs[id] = ms;
    }
    return {
      status: active.status,
      session: active.session,
      errorMessage: active.errorMessage,
      scopeOverrideLabel: active.scopeOverride?.label ?? null,
      tabs: this.tabs.map((tab) => ({
        id: tab.id,
        title: tab.title,
        busy: tab.status === "sending" || tab.status === "streaming",
      })),
      activeTabId: this.activeTabId,
      scopeMode: this.scopeMode,
      durationsMs,
    };
  }

  subscribe(listener: Listener): () => void {
    if (this.disposed) {
      return () => undefined;
    }
    this.listeners.add(listener);
    listener(this.getState());
    return () => {
      this.listeners.delete(listener);
    };
  }

  newTab(): void {
    if (this.disposed) {
      return;
    }
    const tab = this.createEmptyTab();
    this.tabs = [...this.tabs, tab];
    this.activeTabId = tab.id;
    this.notify();
  }

  closeTab(id: string): void {
    if (this.disposed) {
      return;
    }
    const index = this.tabs.findIndex((tab) => tab.id === id);
    if (index < 0) {
      return;
    }
    const tab = this.tabs[index];
    if (!tab) {
      return;
    }
    tab.activeRequest?.abort();
    if (this.tabs.length === 1) {
      const replacement = this.createEmptyTab();
      this.tabs = [replacement];
      this.activeTabId = replacement.id;
      this.notify();
      return;
    }
    const nextTabs = this.tabs.filter((t) => t.id !== id);
    this.tabs = nextTabs;
    if (this.activeTabId === id) {
      const nextActive = nextTabs[Math.min(index, nextTabs.length - 1)];
      this.activeTabId = nextActive?.id ?? nextTabs[0]!.id;
    }
    this.notify();
  }

  switchTab(id: string): void {
    if (this.disposed || !this.tabs.some((tab) => tab.id === id)) {
      return;
    }
    if (this.activeTabId === id) {
      return;
    }
    this.activeTabId = id;
    this.notify();
  }

  setScopeMode(mode: ChatScopeMode): void {
    if (this.disposed || this.scopeMode === mode) {
      return;
    }
    this.scopeMode = mode;
    this.notify();
  }

  focusNote(path: NotePath): void {
    if (this.disposed) {
      return;
    }
    const tab = this.requireActiveTab();
    tab.scopeOverride = {
      scope: SearchScope.currentNote(path),
      label: path.value,
    };
    this.notify();
  }

  clearScopeOverride(): void {
    if (this.disposed) {
      return;
    }
    const tab = this.requireActiveTab();
    if (tab.scopeOverride === null) {
      return;
    }
    tab.scopeOverride = null;
    this.notify();
  }

  async send(text: string): Promise<void> {
    const tab = this.requireActiveTab();
    if (this.disposed || tab.status === "sending" || tab.status === "streaming") {
      return;
    }
    const trimmed = text.trim();
    if (trimmed.length === 0) {
      return;
    }

    const tabId = tab.id;
    tab.activeRequest?.abort();
    const controller = new AbortController();
    tab.activeRequest = controller;

    const showOptimisticTurn = trimmed.length >= MIN_QUERY_LENGTH;
    if (showOptimisticTurn) {
      tab.session = appendPendingQuestion(tab.session, trimmed);
      tab.pendingAssistantMessageId = lastAssistantMessageId(tab.session);
      tab.sendStartedAtMs = this.now();
      if (tab.title === DEFAULT_TAB_TITLE) {
        tab.title = truncateTitle(trimmed);
      }
    } else {
      tab.pendingAssistantMessageId = null;
      tab.sendStartedAtMs = null;
    }
    tab.status = "sending";
    tab.errorMessage = null;
    this.notify();

    try {
      const readiness = await this.deps.ensureRuntime(controller.signal);
      if (!this.isTabRequest(tabId, controller)) {
        return;
      }
      if (!readiness.ok) {
        if (controller.signal.aborted) {
          this.revertOptimisticTurn(tabId, showOptimisticTurn);
          return;
        }
        this.patchTab(tabId, (t) => {
          t.status = "error";
          t.errorMessage = readiness.message;
          if (showOptimisticTurn) {
            t.session = t.session.dropTrailingPending();
            t.pendingAssistantMessageId = null;
            t.sendStartedAtMs = null;
          }
          t.activeRequest = null;
        });
        return;
      }

      const activeTab = this.findTab(tabId);
      if (!activeTab) {
        return;
      }

      let scope: SearchScope;
      if (activeTab.scopeOverride) {
        scope = activeTab.scopeOverride.scope;
        activeTab.scopeOverride = null;
        this.notify();
      } else if (this.deps.resolveScope) {
        scope = await this.deps.resolveScope(this.scopeMode);
      } else {
        scope = SearchScope.entireVault();
      }
      if (!this.isTabRequest(tabId, controller)) {
        return;
      }

      const sessionAtSend = this.findTab(tabId)?.session;
      if (!sessionAtSend) {
        return;
      }

      const result = await this.deps.askQuestion.execute(
        sessionAtSend,
        trimmed,
        scope,
        controller.signal,
        {
          onSessionUpdate: (session) => {
            if (!this.isTabRequest(tabId, controller)) {
              return;
            }
            this.patchTab(tabId, (t) => {
              t.session = session;
              t.status = session.messages.some(
                (message) => message.kind === "assistant" && message.state === "streaming",
              )
                ? "streaming"
                : "sending";
              t.errorMessage = null;
            });
          },
        },
      );

      if (!this.isTabRequest(tabId, controller)) {
        return;
      }

      if (controller.signal.aborted && result.kind === "aborted") {
        this.patchTab(tabId, (t) => {
          t.status = "idle";
          t.errorMessage = null;
          t.session = result.session;
          t.activeRequest = null;
          t.pendingAssistantMessageId = null;
          t.sendStartedAtMs = null;
        });
        return;
      }

      switch (result.kind) {
        case "ok":
          this.finishSend(tabId, controller, {
            status: "idle",
            errorMessage: null,
            session: result.session,
          });
          break;
        case "aborted":
          this.finishSend(tabId, controller, {
            status: "idle",
            errorMessage: null,
            session: result.session,
          });
          break;
        case "validation":
          this.patchTab(tabId, (t) => {
            t.status = "error";
            t.errorMessage = "Question is too short";
            if (showOptimisticTurn) {
              t.session = t.session.dropTrailingPending();
            }
            t.activeRequest = null;
            t.pendingAssistantMessageId = null;
            t.sendStartedAtMs = null;
          });
          break;
        case "error":
          this.recordDurationOnFinish(tabId);
          this.patchTab(tabId, (t) => {
            t.status = "error";
            t.errorMessage = presentError(result.cause).message;
            t.session = result.session;
            t.activeRequest = null;
            t.pendingAssistantMessageId = null;
            t.sendStartedAtMs = null;
          });
          break;
        default: {
          const _exhaustive: never = result;
          return _exhaustive;
        }
      }
    } catch (error) {
      if (!this.isTabRequest(tabId, controller)) {
        return;
      }
      if (controller.signal.aborted || isAbortError(error)) {
        this.revertOptimisticTurn(tabId, showOptimisticTurn);
        return;
      }
      this.patchTab(tabId, (t) => {
        t.status = "error";
        t.errorMessage = presentError(error).message;
        if (showOptimisticTurn) {
          t.session = t.session.dropTrailingPending();
        }
        t.activeRequest = null;
        t.pendingAssistantMessageId = null;
        t.sendStartedAtMs = null;
      });
    }
  }

  cancel(): void {
    const tab = this.requireActiveTab();
    tab.activeRequest?.abort();
    tab.activeRequest = null;
    if (tab.status === "sending" || tab.status === "streaming") {
      tab.status = "idle";
      tab.errorMessage = null;
      this.notify();
    }
  }

  clear(): void {
    const tab = this.requireActiveTab();
    tab.activeRequest?.abort();
    tab.activeRequest = null;
    const hadOverride = tab.scopeOverride !== null;
    tab.scopeOverride = null;
    tab.pendingAssistantMessageId = null;
    tab.sendStartedAtMs = null;
    if (tab.session.messages.length > 0) {
      tab.session = ChatSession.empty(this.createSessionId());
      tab.title = DEFAULT_TAB_TITLE;
      tab.status = "idle";
      tab.errorMessage = null;
      tab.durationsMs = new Map();
      this.notify();
      return;
    }
    if (tab.status !== "idle" || tab.errorMessage !== null || hadOverride) {
      tab.status = "idle";
      tab.errorMessage = null;
      this.notify();
    }
  }

  async openSource(source: SourceReference): Promise<void> {
    await this.deps.openSource(source);
  }

  dispose(): void {
    if (this.disposed) {
      return;
    }
    this.disposed = true;
    for (const tab of this.tabs) {
      tab.activeRequest?.abort();
      tab.activeRequest = null;
    }
    this.listeners.clear();
  }

  private createEmptyTab(): ChatTab {
    return {
      id: crypto.randomUUID(),
      title: DEFAULT_TAB_TITLE,
      session: ChatSession.empty(this.createSessionId()),
      status: "idle",
      errorMessage: null,
      activeRequest: null,
      durationsMs: new Map(),
      scopeOverride: null,
      sendStartedAtMs: null,
      pendingAssistantMessageId: null,
    };
  }

  private createSessionId(): string {
    return this.deps.newSessionId?.() ?? crypto.randomUUID();
  }

  private requireActiveTab(): ChatTab {
    const tab = this.tabs.find((t) => t.id === this.activeTabId);
    if (!tab) {
      throw new Error("Active chat tab missing");
    }
    return tab;
  }

  private findTab(id: string): ChatTab | undefined {
    return this.tabs.find((t) => t.id === id);
  }

  private isTabRequest(tabId: string, controller: AbortController): boolean {
    const tab = this.findTab(tabId);
    return tab !== undefined && tab.activeRequest === controller;
  }

  private patchTab(tabId: string, fn: (tab: ChatTab) => void): void {
    const tab = this.findTab(tabId);
    if (!tab) {
      return;
    }
    fn(tab);
    this.notify();
  }

  private finishSend(
    tabId: string,
    controller: AbortController,
    outcome: { status: ChatStatus; errorMessage: string | null; session: ChatSession },
  ): void {
    this.recordDurationOnFinish(tabId, outcome.session);
    this.patchTab(tabId, (t) => {
      t.status = outcome.status;
      t.errorMessage = outcome.errorMessage;
      t.session = outcome.session;
      t.activeRequest = null;
      t.pendingAssistantMessageId = null;
      t.sendStartedAtMs = null;
    });
  }

  private recordDurationOnFinish(tabId: string, session?: ChatSession): void {
    const tab = this.findTab(tabId);
    if (!tab || tab.sendStartedAtMs === null) {
      return;
    }
    const elapsed = this.now() - tab.sendStartedAtMs;
    let messageId = tab.pendingAssistantMessageId;
    if (!messageId && session) {
      messageId = lastAssistantMessageId(session);
    }
    if (messageId) {
      tab.durationsMs.set(messageId, elapsed);
    }
  }

  private revertOptimisticTurn(tabId: string, showOptimisticTurn: boolean): void {
    this.patchTab(tabId, (t) => {
      t.status = "idle";
      t.errorMessage = null;
      t.activeRequest = null;
      t.pendingAssistantMessageId = null;
      t.sendStartedAtMs = null;
      if (showOptimisticTurn) {
        t.session = t.session.dropTrailingPending();
      }
    });
  }

  private notify(): void {
    const snapshot = this.getState();
    for (const listener of this.listeners) {
      listener(snapshot);
    }
  }
}

function appendPendingQuestion(session: ChatSession, text: string): ChatSession {
  return session
    .appendMessage(ChatMessageEntity.user(text))
    .appendMessage(ChatMessageEntity.assistant("", { state: "pending" }));
}

function lastAssistantMessageId(session: ChatSession): string | null {
  for (let i = session.messages.length - 1; i >= 0; i -= 1) {
    const message = session.messages[i];
    if (message?.kind === "assistant") {
      return message.id;
    }
  }
  return null;
}

function truncateTitle(text: string): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= TAB_TITLE_MAX) {
    return normalized;
  }
  return `${normalized.slice(0, TAB_TITLE_MAX - 1)}…`;
}
