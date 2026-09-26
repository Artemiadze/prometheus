import { describe, expect, it } from "vitest";

import {
  messageRenderKey,
  planMessageRender,
} from "../../../../../src/adapters/inbound/obsidian/chat/planMessageRender";
import { ChatMessage } from "../../../../../src/domain/entities/ChatMessage";

describe("planMessageRender", () => {
  it("detects changed message keys", () => {
    const user = ChatMessage.user("Hello");
    const pending = ChatMessage.assistant("", { state: "pending" });
    const complete = ChatMessage.assistant("Done", { id: pending.id, state: "complete" });
    const prev = [messageRenderKey(user), messageRenderKey(pending)];
    const next = [messageRenderKey(user), messageRenderKey(complete)];
    expect(planMessageRender(prev, [user, complete])).toEqual([next[1]]);
  });
});
