import { describe, expect, it, vi } from "vitest";

import { ChatStore } from "../../../../../src/adapters/inbound/obsidian/chat/ChatStore";
import type { AskQuestionResult } from "../../../../../src/application/use-cases/AskQuestion";
import { ChatSession } from "../../../../../src/domain/entities/ChatSession";
import { ChatMessage } from "../../../../../src/domain/entities/ChatMessage";
describe("ChatStore", () => {
  it("ignores empty send and duplicate sends while busy", async () => {
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
      newSessionId: () => "session-1",
    });

    const send1 = store.send("hello world");
    await Promise.resolve();
    await store.send("second question");
    expect(askQuestion.execute).toHaveBeenCalledTimes(1);

    resolveChat({
      kind: "ok",
      session: ChatSession.empty("session-1")
        .appendMessage(ChatMessage.user("hello world"))
        .appendMessage(ChatMessage.assistant("ok", { state: "complete" })),
    });
    await send1;
  });

  it("notifies subscribers only when state changes", async () => {
    const { AskQuestion } = await import("../../../../../src/application/use-cases/AskQuestion");
    const { FakeRagGateway } = await import("../../../../fakes/FakeRagGateway");
    const { FakeSettingsRepository } = await import("../../../../fakes/FakeSettingsRepository");
    const { DEFAULT_PLUGIN_SETTINGS } = await import("../../../../../src/application/dto/settings");
    const store = new ChatStore({
      askQuestion: new AskQuestion(
        new FakeRagGateway(),
        new FakeSettingsRepository({ ...DEFAULT_PLUGIN_SETTINGS, vaultId: "vault-a1" }),
      ),
      ensureRuntime: async () => ({ ok: true }),
      openSource: async () => undefined,
      newSessionId: () => "session-1",
    });
    let notifications = 0;
    store.subscribe(() => {
      notifications += 1;
    });
    expect(notifications).toBe(1);
    store.clear();
    expect(notifications).toBe(1);
    await store.send("no");
    expect(notifications).toBe(3);
    store.clear();
    expect(notifications).toBe(4);
    store.clear();
    expect(notifications).toBe(4);
  });

  it("maps validation and runtime missing to error status", async () => {
    const { AskQuestion } = await import("../../../../../src/application/use-cases/AskQuestion");
    const { FakeRagGateway } = await import("../../../../fakes/FakeRagGateway");
    const { FakeSettingsRepository } = await import("../../../../fakes/FakeSettingsRepository");
    const { DEFAULT_PLUGIN_SETTINGS } = await import("../../../../../src/application/dto/settings");
    const store = new ChatStore({
      askQuestion: new AskQuestion(
        new FakeRagGateway(),
        new FakeSettingsRepository({ ...DEFAULT_PLUGIN_SETTINGS, vaultId: "vault-a1" }),
      ),
      ensureRuntime: async () => ({ ok: true }),
      openSource: async () => undefined,
      newSessionId: () => "session-1",
    });
    await store.send("hi");
    expect(store.getState().status).toBe("error");
    expect(store.getState().errorMessage).toBe("Question is too short");

    const missing = new ChatStore({
      askQuestion: { execute: vi.fn() },
      ensureRuntime: async () => ({ ok: false, message: "Runtime missing" }),
      openSource: async () => undefined,
      newSessionId: () => "session-2",
    });
    await missing.send("hello there");
    expect(missing.getState().status).toBe("error");
    expect(missing.getState().errorMessage).toBe("Runtime missing");
  });

  it("returns to idle after abort and clears session", async () => {
    const { AskQuestion } = await import("../../../../../src/application/use-cases/AskQuestion");
    const { FakeRagGateway } = await import("../../../../fakes/FakeRagGateway");
    const { FakeSettingsRepository } = await import("../../../../fakes/FakeSettingsRepository");
    const { DEFAULT_PLUGIN_SETTINGS } = await import("../../../../../src/application/dto/settings");
    const rag = new FakeRagGateway();
    rag.chatDelayMs = 100;
    const store = new ChatStore({
      askQuestion: new AskQuestion(
        rag,
        new FakeSettingsRepository({ ...DEFAULT_PLUGIN_SETTINGS, vaultId: "vault-a1" }),
      ),
      ensureRuntime: async () => ({ ok: true }),
      openSource: async () => undefined,
      newSessionId: () => "session-1",
    });
    const pending = store.send("hello there");
    await Promise.resolve();
    store.cancel();
    await pending;
    expect(store.getState().status).toBe("idle");

    store.clear();
    expect(store.getState().session.messages).toHaveLength(0);
  });

  it("dispose stops further notifications", () => {
    const store = new ChatStore({
      askQuestion: { execute: vi.fn() },
      ensureRuntime: async () => ({ ok: true }),
      openSource: async () => undefined,
    });
    let count = 0;
    store.subscribe(() => {
      count += 1;
    });
    store.dispose();
    store.clear();
    expect(count).toBe(1);
  });

  it("passes resolved scope into AskQuestion", async () => {
    const { SearchScope } = await import("../../../../../src/domain/value-objects/SearchScope");
    const { NotePath } = await import("../../../../../src/domain/value-objects/NotePath");
    const askQuestion = {
      execute: vi.fn(async (): Promise<AskQuestionResult> => ({
        kind: "ok",
        session: ChatSession.empty("session-1")
          .appendMessage(ChatMessage.user("hello world"))
          .appendMessage(ChatMessage.assistant("ok", { state: "complete" })),
      })),
    };
    const scoped = SearchScope.currentNote(NotePath.create("notes/a.md"));
    const store = new ChatStore({
      askQuestion,
      ensureRuntime: async () => ({ ok: true }),
      openSource: async () => undefined,
      resolveScope: async () => scoped,
    });
    await store.send("hello world");
    expect(askQuestion.execute).toHaveBeenCalledWith(
      expect.anything(),
      "hello world",
      scoped,
      expect.anything(),
    );
  });
});
