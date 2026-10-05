import type { ChatMessage } from "./ChatMessage";

/**
 * In-memory ordered set of chat messages. MVP does not persist history.
 */
export class ChatSession {
  readonly id: string;
  private readonly _messages: readonly ChatMessage[];

  private constructor(id: string, messages: readonly ChatMessage[]) {
    this.id = id;
    this._messages = messages;
  }

  static empty(id: string): ChatSession {
    return new ChatSession(id, []);
  }

  get messages(): readonly ChatMessage[] {
    return this._messages;
  }

  appendMessage(message: ChatMessage): ChatSession {
    return new ChatSession(this.id, [...this._messages, message]);
  }

  replaceMessage(id: string, message: ChatMessage): ChatSession {
    const index = this._messages.findIndex((item) => item.id === id);
    if (index < 0) {
      throw new Error(`Message not found: ${id}`);
    }
    const next = [...this._messages];
    next[index] = message;
    return new ChatSession(this.id, next);
  }

  /** Removes a trailing in-flight assistant placeholder (e.g. after runtime startup failure). */
  dropTrailingPending(): ChatSession {
    const last = this._messages[this._messages.length - 1];
    if (last?.kind !== "assistant" || last.state !== "pending") {
      return this;
    }
    return new ChatSession(this.id, this._messages.slice(0, -1));
  }
}
