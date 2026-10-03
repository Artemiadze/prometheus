import type { AskQuestion } from "../../../../application/use-cases/AskQuestion";
import { MIN_QUERY_LENGTH } from "../../../../application/use-cases/SearchNotes";
import { ChatSession } from "../../../../domain/entities/ChatSession";
import type { ChatMessage } from "../../../../domain/entities/ChatMessage";
import { ChatMessage as ChatMessageEntity } from "../../../../domain/entities/ChatMessage";
import { isAbortError } from "../../../../domain/errors";
import type { SourceReference } from "../../../../domain/entities/SourceReference";
import type { NotePath } from "../../../../domain/value-objects/NotePath";
import { SearchScope } from "../../../../domain/value-objects/SearchScope";
import { presentError } from "../errors/presentError";

export type ChatStatus = "idle" | "sending" | "streaming" | "error";

export type ChatViewState = {
  readonly status: ChatStatus;
  readonly session: ChatSession;
  readonly errorMessage: string | null;
  readonly scopeOverrideLabel: string | null;
};

export type ChatRuntimeReadiness =
  { readonly ok: true } | { readonly ok: false; readonly message: string };

export type ChatStoreDeps = {
  readonly askQuestion: Pick<AskQuestion, "execute">;
  readonly ensureRuntime: (signal: AbortSignal) => Promise<ChatRuntimeReadiness>;
  readonly openSource: (source: SourceReference) => Promise<void>;
  readonly resolveScope?: (() => Promise<SearchScope>) | undefined;
  readonly newSessionId?: (() => string) | undefined;
};

type ScopeOverride = {
  readonly scope: SearchScope;
  readonly label: string;
};

type Listener = (state: ChatViewState) => void;

export class ChatStore {
  private session: ChatSession;
  private status: ChatStatus = "idle";
  private errorMessage: string | null = null;
  private scopeOverride: ScopeOverride | null = null;
  private readonly listeners = new Set<Listener>();
  private activeRequest: AbortController | null = null;
  private disposed = false;

  constructor(private readonly deps: ChatStoreDeps) {
    this.session = ChatSession.empty(this.createSessionId());
  }

  getState(): ChatViewState {
    return {
      status: this.status,
      session: this.session,
      errorMessage: this.errorMessage,
      scopeOverrideLabel: this.scopeOverride?.label ?? null,
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

  focusNote(path: NotePath): void {
    if (this.disposed) {
      return;
    }
    this.scopeOverride = {
      scope: SearchScope.currentNote(path),
      label: path.value,
    };
    this.notify();
  }

  clearScopeOverride(): void {
    if (this.disposed || this.scopeOverride === null) {
      return;
    }
    this.scopeOverride = null;
    this.notify();
  }

  async send(text: string): Promise<void> {
    if (this.disposed || this.status === "sending" || this.status === "streaming") {
      return;
    }
    const trimmed = text.trim();
    if (trimmed.length === 0) {
      return;
    }

    this.activeRequest?.abort();
    const controller = new AbortController();
    this.activeRequest = controller;

    const showOptimisticTurn = trimmed.length >= MIN_QUERY_LENGTH;
    this.setState({
      status: "sending",
      errorMessage: null,
      ...(showOptimisticTurn
        ? { session: appendPendingQuestion(this.session, trimmed) }
        : {}),
    });

    try {
      const readiness = await this.deps.ensureRuntime(controller.signal);
      if (this.activeRequest !== controller) {
        return;
      }
      if (!readiness.ok) {
        if (controller.signal.aborted) {
          this.revertOptimisticTurn(showOptimisticTurn);
          return;
        }
        this.setState({
          status: "error",
          errorMessage: readiness.message,
          session: showOptimisticTurn ? this.session.dropTrailingPending() : this.session,
        });
        this.activeRequest = null;
        return;
      }

      let scope: SearchScope;
      if (this.scopeOverride) {
        scope = this.scopeOverride.scope;
        this.scopeOverride = null;
        this.notify();
      } else if (this.deps.resolveScope) {
        scope = await this.deps.resolveScope();
      } else {
        scope = SearchScope.entireVault();
      }
      if (this.activeRequest !== controller) {
        return;
      }

      const result = await this.deps.askQuestion.execute(
        this.session,
        trimmed,
        scope,
        controller.signal,
        {
          onSessionUpdate: (session) => {
            if (this.activeRequest !== controller) {
              return;
            }
            this.setState({
              status: session.messages.some(
                (message) => message.kind === "assistant" && message.state === "streaming",
              )
                ? "streaming"
                : "sending",
              errorMessage: null,
              session,
            });
          },
        },
      );

      if (this.activeRequest !== controller) {
        return;
      }

      if (controller.signal.aborted && result.kind === "aborted") {
        this.setState({ status: "idle", errorMessage: null, session: result.session });
        this.activeRequest = null;
        return;
      }

      switch (result.kind) {
        case "ok":
          this.setState({ status: "idle", errorMessage: null, session: result.session });
          break;
        case "aborted":
          this.setState({ status: "idle", errorMessage: null, session: result.session });
          break;
        case "validation":
          this.setState({
            status: "error",
            errorMessage: "Question is too short",
            session: showOptimisticTurn ? this.session.dropTrailingPending() : this.session,
          });
          break;
        case "error":
          this.setState({
            status: "error",
            errorMessage: presentError(result.cause).message,
            session: result.session,
          });
          break;
        default: {
          const _exhaustive: never = result;
          return _exhaustive;
        }
      }
      this.activeRequest = null;
    } catch (error) {
      if (this.activeRequest !== controller) {
        return;
      }
      if (controller.signal.aborted || isAbortError(error)) {
        this.revertOptimisticTurn(showOptimisticTurn);
        this.activeRequest = null;
        return;
      }
      this.setState({
        status: "error",
        errorMessage: presentError(error).message,
        session: showOptimisticTurn ? this.session.dropTrailingPending() : this.session,
      });
      this.activeRequest = null;
    }
  }

  cancel(): void {
    this.activeRequest?.abort();
    this.activeRequest = null;
    if (this.status === "sending" || this.status === "streaming") {
      this.setState({ status: "idle", errorMessage: null });
    }
  }

  clear(): void {
    this.activeRequest?.abort();
    this.activeRequest = null;
    const hadOverride = this.scopeOverride !== null;
    this.scopeOverride = null;
    if (this.session.messages.length > 0) {
      this.setState({
        status: "idle",
        errorMessage: null,
        session: ChatSession.empty(this.createSessionId()),
      });
      return;
    }
    if (this.status !== "idle" || this.errorMessage !== null || hadOverride) {
      this.setState({ status: "idle", errorMessage: null });
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
    this.activeRequest?.abort();
    this.activeRequest = null;
    this.listeners.clear();
  }

  private createSessionId(): string {
    return this.deps.newSessionId?.() ?? crypto.randomUUID();
  }

  private revertOptimisticTurn(showOptimisticTurn: boolean): void {
    if (!showOptimisticTurn) {
      this.setState({ status: "idle", errorMessage: null });
      return;
    }
    this.setState({
      status: "idle",
      errorMessage: null,
      session: this.session.dropTrailingPending(),
    });
  }

  private setState(
    partial: Partial<Pick<ChatViewState, "status" | "session" | "errorMessage">>,
  ): void {
    const nextStatus = partial.status ?? this.status;
    const nextSession = partial.session ?? this.session;
    const nextError = partial.errorMessage !== undefined ? partial.errorMessage : this.errorMessage;
    const changed =
      nextStatus !== this.status ||
      !sessionsEqual(nextSession, this.session) ||
      nextError !== this.errorMessage;
    if (!changed) {
      return;
    }
    this.status = nextStatus;
    this.session = nextSession;
    this.errorMessage = nextError;
    this.notify();
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

function sessionsEqual(left: ChatSession, right: ChatSession): boolean {
  if (left.id !== right.id || left.messages.length !== right.messages.length) {
    return false;
  }
  return left.messages.every((message, index) => messagesEqual(message, right.messages[index]));
}

function messagesEqual(left: ChatMessage | undefined, right: ChatMessage | undefined): boolean {
  if (!left || !right) {
    return false;
  }
  if (left.id !== right.id || left.kind !== right.kind || left.state !== right.state) {
    return false;
  }
  if (left.text !== right.text) {
    return false;
  }
  if (left.kind === "assistant" && right.kind === "assistant") {
    return (
      left.insufficientContext === right.insufficientContext &&
      left.sources.length === right.sources.length
    );
  }
  return true;
}
