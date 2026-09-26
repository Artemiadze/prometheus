import { describe, expect, it } from "vitest";

import { InvariantViolationError } from "../errors";
import { SourceReference } from "./SourceReference";
import { ChatMessage } from "./ChatMessage";
import { ChatSession } from "./ChatSession";

describe("ChatMessage", () => {
  it("rejects empty user messages", () => {
    expect(() => ChatMessage.user("")).toThrow(InvariantViolationError);
    expect(() => ChatMessage.user("   ")).toThrow(InvariantViolationError);
  });

  it("allows assistant messages with sources and insufficient-context flag", () => {
    const source = SourceReference.create("notes/a.md", "Intro");
    const message = ChatMessage.assistant("Answer", {
      sources: [source],
      insufficientContext: true,
      state: "complete",
    });
    expect(message.kind).toBe("assistant");
    expect(message.sources).toEqual([source]);
    expect(message.insufficientContext).toBe(true);
  });
});

describe("ChatSession", () => {
  it("replaces a message by id", () => {
    const pending = ChatMessage.assistant("", { state: "pending" });
    const session = ChatSession.empty("session-1").appendMessage(pending);
    const complete = ChatMessage.assistant("Done", { id: pending.id, state: "complete" });
    const next = session.replaceMessage(pending.id, complete);
    expect(next.messages[0]?.kind).toBe("assistant");
    if (next.messages[0]?.kind === "assistant") {
      expect(next.messages[0].state).toBe("complete");
    }
  });

  it("appends messages immutably and preserves order", () => {
    const session = ChatSession.empty("session-1");
    const user = ChatMessage.user("Hello");
    const assistant = ChatMessage.assistant("Hi");
    const next = session.appendMessage(user).appendMessage(assistant);

    expect(session.messages).toHaveLength(0);
    expect(next.messages.map((m) => m.kind)).toEqual(["user", "assistant"]);
    expect(next.id).toBe("session-1");
  });
});
