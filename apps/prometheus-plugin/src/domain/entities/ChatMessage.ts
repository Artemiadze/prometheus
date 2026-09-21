import { InvariantViolationError } from "../errors";
import type { SourceReference } from "./SourceReference";

export type UserMessageState = "pending" | "complete" | "error" | "cancelled";
export type AssistantMessageState = "pending" | "streaming" | "complete" | "error" | "cancelled";

export type UserChatMessage = {
  readonly kind: "user";
  readonly id: string;
  readonly text: string;
  readonly createdAt: Date;
  readonly state: UserMessageState;
};

export type AssistantChatMessage = {
  readonly kind: "assistant";
  readonly id: string;
  readonly text: string;
  readonly createdAt: Date;
  readonly state: AssistantMessageState;
  readonly sources: readonly SourceReference[];
  readonly insufficientContext: boolean;
};

export type ChatMessage = UserChatMessage | AssistantChatMessage;

export type AssistantMessageOptions = {
  readonly sources?: readonly SourceReference[];
  readonly insufficientContext?: boolean;
  readonly state?: AssistantMessageState;
  readonly id?: string;
  readonly createdAt?: Date;
};

let messageCounter = 0;

function nextId(prefix: string): string {
  messageCounter += 1;
  return `${prefix}-${messageCounter}`;
}

export const ChatMessage = {
  user(
    text: string,
    options: { id?: string; createdAt?: Date; state?: UserMessageState } = {},
  ): UserChatMessage {
    const trimmed = text.trim();
    if (!trimmed) {
      throw new InvariantViolationError();
    }
    return {
      kind: "user",
      id: options.id ?? nextId("user"),
      text: trimmed,
      createdAt: options.createdAt ?? new Date(),
      state: options.state ?? "complete",
    };
  },

  assistant(text: string, options: AssistantMessageOptions = {}): AssistantChatMessage {
    return {
      kind: "assistant",
      id: options.id ?? nextId("assistant"),
      text,
      createdAt: options.createdAt ?? new Date(),
      state: options.state ?? "complete",
      sources: options.sources ?? [],
      insufficientContext: options.insufficientContext ?? false,
    };
  },
};
