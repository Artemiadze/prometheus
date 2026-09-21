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
}
