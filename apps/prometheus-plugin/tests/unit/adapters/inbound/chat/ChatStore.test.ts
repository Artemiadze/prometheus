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
      newSessionId: () => "session-1",
    });
    await store.send("hello world");
    expect(askQuestion.execute).toHaveBeenCalledWith(
      expect.anything(),
      "hello world",
      scoped,
      expect.anything(),
      expect.anything(),
    );
  });

  it("focusNote pins scope for the next message only", async () => {
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
    const defaultScope = SearchScope.entireVault();
    const store = new ChatStore({
      askQuestion,
      ensureRuntime: async () => ({ ok: true }),
      openSource: async () => undefined,
      resolveScope: async (_mode) => defaultScope,
      newSessionId: () => "session-1",
    });
    const note = NotePath.create("notes/pinned.md");
    store.focusNote(note);
    expect(store.getState().scopeOverrideLabel).toBe("notes/pinned.md");

    await store.send("hello world");
    expect(askQuestion.execute).toHaveBeenCalledWith(
      expect.anything(),
      "hello world",
      SearchScope.currentNote(note),
      expect.anything(),
      expect.anything(),
    );
    expect(store.getState().scopeOverrideLabel).toBeNull();

    await store.send("second question");
    expect(askQuestion.execute).toHaveBeenLastCalledWith(
      expect.anything(),
      "second question",
      defaultScope,
      expect.anything(),
      expect.anything(),
    );
  });

  it("keeps focusNote pin after runtime failure and clears via clear/clearScopeOverride", async () => {
    const { NotePath } = await import("../../../../../src/domain/value-objects/NotePath");
    const store = new ChatStore({
      askQuestion: { execute: vi.fn() },
      ensureRuntime: async () => ({ ok: false, message: "Runtime missing" }),
      openSource: async () => undefined,
    });
    store.focusNote(NotePath.create("a.md"));
    await store.send("hello world");
    expect(store.getState().scopeOverrideLabel).toBe("a.md");

    store.clearScopeOverride();
    expect(store.getState().scopeOverrideLabel).toBeNull();

    store.focusNote(NotePath.create("b.md"));
    store.clear();
    expect(store.getState().scopeOverrideLabel).toBeNull();
  });

  it("creates, switches, and closes tabs while keeping at least one", () => {
    const store = new ChatStore({
      askQuestion: { execute: vi.fn() },
      ensureRuntime: async () => ({ ok: true }),
      openSource: async () => undefined,
    });
    expect(store.getState().tabs).toHaveLength(1);
    const firstId = store.getState().activeTabId;
    store.newTab();
    expect(store.getState().tabs).toHaveLength(2);
    const secondId = store.getState().activeTabId;
    expect(secondId).not.toBe(firstId);
    store.switchTab(firstId);
    expect(store.getState().activeTabId).toBe(firstId);
    store.closeTab(firstId);
    expect(store.getState().tabs).toHaveLength(1);
    expect(store.getState().activeTabId).toBe(secondId);
    store.closeTab(secondId);
    expect(store.getState().tabs).toHaveLength(1);
  });

  it("sets tab title from the first question", async () => {
    const askQuestion = {
      execute: vi.fn(async (): Promise<AskQuestionResult> => ({
        kind: "ok",
        session: ChatSession.empty("session-1")
          .appendMessage(ChatMessage.user("What is sparse attention?"))
          .appendMessage(ChatMessage.assistant("Answer", { state: "complete" })),
      })),
    };
    const store = new ChatStore({
      askQuestion,
      ensureRuntime: async () => ({ ok: true }),
      openSource: async () => undefined,
      newSessionId: () => "session-1",
    });
    await store.send("What is sparse attention?");
    expect(store.getState().tabs[0]?.title).toBe("What is sparse attention?");
  });

  it("passes scope mode into resolveScope", async () => {
    const { SearchScope } = await import("../../../../../src/domain/value-objects/SearchScope");
    const resolveScope = vi.fn(async () => SearchScope.entireVault());
    const askQuestion = {
      execute: vi.fn(async (): Promise<AskQuestionResult> => ({
        kind: "ok",
        session: ChatSession.empty("session-1")
          .appendMessage(ChatMessage.user("hello world"))
          .appendMessage(ChatMessage.assistant("ok", { state: "complete" })),
      })),
    };
    const store = new ChatStore({
      askQuestion,
      ensureRuntime: async () => ({ ok: true }),
      openSource: async () => undefined,
      resolveScope,
    });
    store.setScopeMode("current_note");
    await store.send("hello world");
    expect(resolveScope).toHaveBeenCalledWith("current_note");
  });

  it("records assistant response duration", async () => {
    let now = 1_000;
    const askQuestion = {
      execute: vi.fn(async (): Promise<AskQuestionResult> => {
        now += 5_000;
        const session = ChatSession.empty("session-1")
          .appendMessage(ChatMessage.user("hello world"))
          .appendMessage(ChatMessage.assistant("done", { state: "complete", id: "assistant-1" }));
        return { kind: "ok", session };
      }),
    };
    const store = new ChatStore({
      askQuestion,
      ensureRuntime: async () => ({ ok: true }),
      openSource: async () => undefined,
      newSessionId: () => "session-1",
      now: () => now,
    });
    await store.send("hello world");
    const durations = Object.values(store.getState().durationsMs);
    expect(durations).toContain(5_000);
  });

  it("continues streaming updates on a background tab", async () => {
    let resolveChat = (_value: AskQuestionResult): void => undefined;
    let onUpdate: ((session: ChatSession) => void) | undefined;
    const askQuestion = {
      execute: vi.fn(
        (
          _session,
          _text,
          _scope,
          _signal,
          callbacks?: { onSessionUpdate?: (session: ChatSession) => void },
        ): Promise<AskQuestionResult> => {
          onUpdate = callbacks?.onSessionUpdate;
          return new Promise((resolve) => {
            resolveChat = resolve;
          });
        },
      ),
    };
    const store = new ChatStore({
      askQuestion,
      ensureRuntime: async () => ({ ok: true }),
      openSource: async () => undefined,
      newSessionId: () => "session-1",
    });
    store.newTab();
    const backgroundTabId = store.getState().activeTabId;
    const sendPromise = store.send("hello world");
    await Promise.resolve();
    const foregroundTabId = store.getState().tabs[0]?.id;
    if (foregroundTabId) {
      store.switchTab(foregroundTabId);
    }
    expect(store.getState().activeTabId).not.toBe(backgroundTabId);

    const streamingSession = ChatSession.empty("session-1")
      .appendMessage(ChatMessage.user("hello world"))
      .appendMessage(ChatMessage.assistant("partial", { state: "streaming", id: "a1" }));
    onUpdate?.(streamingSession);
    expect(store.getState().tabs.find((t) => t.id === backgroundTabId)?.busy).toBe(true);

    resolveChat({
      kind: "ok",
      session: streamingSession.replaceMessage(
        "a1",
        ChatMessage.assistant("done", { state: "complete", id: "a1" }),
      ),
    });
    await sendPromise;
    expect(store.getState().tabs.find((t) => t.id === backgroundTabId)?.busy).toBe(false);
  });
});
