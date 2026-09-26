import type { AskQuestion } from "../../../../application/use-cases/AskQuestion";
import { ChatSession } from "../../../../domain/entities/ChatSession";
import type { ChatMessage } from "../../../../domain/entities/ChatMessage";
import type { SourceReference } from "../../../../domain/entities/SourceReference";
import { SearchScope } from "../../../../domain/value-objects/SearchScope";

export type ChatStatus = "idle" | "sending" | "streaming" | "error";

export type ChatViewState = {
  readonly status: ChatStatus;
  readonly session: ChatSession;
  readonly errorMessage: string | null;
};

export type ChatRuntimeReadiness =
  { readonly ok: true } | { readonly ok: false; readonly message: string };

export type ChatStoreDeps = {
  readonly askQuestion: Pick<AskQuestion, "execute">;
  readonly ensureRuntime: (signal: AbortSignal) => Promise<ChatRuntimeReadiness>;
  readonly openSource: (source: SourceReference) => Promise<void>;
  readonly newSessionId?: () => string;
};

type Listener = (state: ChatViewState) => void;

export class ChatStore {
  private session: ChatSession;
  private status: ChatStatus = "idle";
  private errorMessage: string | null = null;
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

  async send(text: string): Promise<void> {
    if (this.disposed || this.status === "sending") {
      return;
    }
    const trimmed = text.trim();
    if (trimmed.length === 0) {
      return;
    }

    this.activeRequest?.abort();
    const controller = new AbortController();
    this.activeRequest = controller;
    this.setState({ status: "sending", errorMessage: null });

    const readiness = await this.deps.ensureRuntime(controller.signal);
    if (this.activeRequest !== controller) {
      return;
    }
    if (!readiness.ok) {
      if (controller.signal.aborted) {
        return;
      }
      this.setState({ status: "error", errorMessage: readiness.message });
      this.activeRequest = null;
      return;
    }

    const result = await this.deps.askQuestion.execute(
      this.session,
      trimmed,
      SearchScope.entireVault(),
      controller.signal,
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
        this.setState({ status: "error", errorMessage: "Question is too short" });
        break;
      case "error":
        this.setState({
          status: "error",
          errorMessage: "Unable to answer the question.",
          session: result.session,
        });
        break;
      default: {
        const _exhaustive: never = result;
        return _exhaustive;
      }
    }
    this.activeRequest = null;
  }

  cancel(): void {
    this.activeRequest?.abort();
    this.activeRequest = null;
    if (this.status === "sending") {
      this.setState({ status: "idle", errorMessage: null });
    }
  }

  clear(): void {
    this.activeRequest?.abort();
    this.activeRequest = null;
    if (this.session.messages.length > 0) {
      this.setState({
        status: "idle",
        errorMessage: null,
        session: ChatSession.empty(this.createSessionId()),
      });
      return;
    }
    if (this.status !== "idle" || this.errorMessage !== null) {
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
    const snapshot = this.getState();
    for (const listener of this.listeners) {
      listener(snapshot);
    }
  }
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
