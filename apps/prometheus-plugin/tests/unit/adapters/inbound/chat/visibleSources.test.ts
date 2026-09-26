import { describe, expect, it } from "vitest";

import { visibleSources } from "../../../../../src/adapters/inbound/obsidian/chat/visibleSources";
import { ChatMessage } from "../../../../../src/domain/entities/ChatMessage";
import { SourceReference } from "../../../../../src/domain/entities/SourceReference";

describe("visibleSources", () => {
  it("hides sources for insufficient context and non-complete states", () => {
    const source = SourceReference.create("a.md", "Intro");
    const insufficient = ChatMessage.assistant("No data", {
      state: "complete",
      insufficientContext: true,
      sources: [source],
    });
    expect(visibleSources(insufficient)).toEqual([]);

    const pending = ChatMessage.assistant("", { state: "pending", sources: [source] });
    expect(visibleSources(pending)).toEqual([]);
  });

  it("returns sources for complete grounded answers", () => {
    const source = SourceReference.create("a.md", "Intro");
    const message = ChatMessage.assistant("Answer", {
      state: "complete",
      sources: [source],
    });
    expect(visibleSources(message)).toEqual([source]);
  });
});
