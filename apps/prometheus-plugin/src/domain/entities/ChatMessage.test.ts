import { describe, expect, it } from "vitest";

import { ChatMessage } from "./ChatMessage";
import { SourceReference } from "./SourceReference";
import { InvariantViolationError } from "../errors";

describe("ChatMessage", () => {
  it("creates user and assistant messages with defaults", () => {
    const user = ChatMessage.user("  hello  ");
    expect(user.kind).toBe("user");
    expect(user.text).toBe("hello");
    expect(user.state).toBe("complete");

    const assistant = ChatMessage.assistant("answer", {
      sources: [SourceReference.create("a.md", "H1")],
      insufficientContext: true,
      state: "complete",
    });
    expect(assistant.kind).toBe("assistant");
    expect(assistant.insufficientContext).toBe(true);
    expect(assistant.sources).toHaveLength(1);
  });

  it("rejects blank user text", () => {
    expect(() => ChatMessage.user("   ")).toThrow(InvariantViolationError);
  });
});
