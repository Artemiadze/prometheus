import { describe, expect, it, vi } from "vitest";

import { ChatStore } from "../../../../../src/adapters/inbound/obsidian/chat/ChatStore";
import type { AskQuestionResult } from "../../../../../src/application/use-cases/AskQuestion";
import { ChatMessage } from "../../../../../src/domain/entities/ChatMessage";
import { ChatSession } from "../../../../../src/domain/entities/ChatSession";
import { SourceReference } from "../../../../../src/domain/entities/SourceReference";

/**
 * PLG-85 — ChatStore UI states without Obsidian DOM.
 * Covers idle, loading (sending), error, empty session, and success.
 */
describe("ChatStore UI states (PLG-85)", () => {
  it("starts idle with an empty session (empty)", () => {
    const store = new ChatStore({
      askQuestion: { execute: vi.fn() },
      ensureRuntime: async () => ({ ok: true }),
      openSource: async () => undefined,
      newSessionId: () => "session-ui",
    });
    const state = store.getState();
    expect(state.status).toBe("idle");
    expect(state.errorMessage).toBeNull();
    expect(state.session.messages).toHaveLength(0);
    store.dispose();
  });

  it("enters sending (loading) then idle on success", async () => {
    let resolveChat = (_value: AskQuestionResult): void => undefined;
    const askQuestion = {
      execute: vi.fn(
        (): Promise<AskQuestionResult> =>
          new Promise((resolve) => {
            resolveChat = resolve;
          }),
      ),
    };
    const store = new ChatStore({
      askQuestion,
      ensureRuntime: async () => ({ ok: true }),
      openSource: async () => undefined,
      newSessionId: () => "session-ui",
    });

    const pending = store.send("hello world");
    await Promise.resolve();
    expect(store.getState().status).toBe("sending");
    expect(store.getState().errorMessage).toBeNull();
    expect(store.getState().session.messages).toHaveLength(2);
    expect(store.getState().session.messages[0]?.kind).toBe("user");

    const session = ChatSession.empty("session-ui")
      .appendMessage(ChatMessage.user("hello world"))
      .appendMessage(
        ChatMessage.assistant("Grounded answer", {
          state: "complete",
          sources: [SourceReference.create("a.md", null)],
          insufficientContext: false,
        }),
      );
    resolveChat({ kind: "ok", session });
    await pending;

    expect(store.getState().status).toBe("idle");
    expect(store.getState().session.messages).toHaveLength(2);
    expect(store.getState().errorMessage).toBeNull();
    store.dispose();
  });

  it("maps insufficient-context success without error status", async () => {
    const session = ChatSession.empty("session-ui")
      .appendMessage(ChatMessage.user("obscure question here"))
      .appendMessage(
        ChatMessage.assistant("Not enough notes matched.", {
          state: "complete",
          insufficientContext: true,
        }),
      );
    const store = new ChatStore({
      askQuestion: {
        execute: async () => ({ kind: "ok" as const, session }),
      },
      ensureRuntime: async () => ({ ok: true }),
      openSource: async () => undefined,
      newSessionId: () => "session-ui",
    });
    await store.send("obscure question here");
    const assistant = store.getState().session.messages[1];
    expect(store.getState().status).toBe("idle");
    expect(assistant?.kind).toBe("assistant");
    if (assistant?.kind === "assistant") {
      expect(assistant.insufficientContext).toBe(true);
    }
    store.dispose();
  });

  it("enters error on runtime failure and clears back to idle", async () => {
    const store = new ChatStore({
      askQuestion: { execute: vi.fn() },
      ensureRuntime: async () => ({ ok: false, message: "Runtime is not ready" }),
      openSource: async () => undefined,
      newSessionId: () => "session-ui",
    });
    await store.send("hello world");
    expect(store.getState().status).toBe("error");
    expect(store.getState().errorMessage).toBe("Runtime is not ready");

    store.clear();
    expect(store.getState().status).toBe("idle");
    expect(store.getState().errorMessage).toBeNull();
    store.dispose();
  });
});
