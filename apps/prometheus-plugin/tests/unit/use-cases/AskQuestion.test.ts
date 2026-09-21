import { describe, expect, it } from "vitest";

import { AskQuestion } from "../../../src/application/use-cases/AskQuestion";
import { DEFAULT_PLUGIN_SETTINGS } from "../../../src/application/dto/settings";
import { ChatSession } from "../../../src/domain/entities/ChatSession";
import { SourceReference } from "../../../src/domain/entities/SourceReference";
import { SearchScope } from "../../../src/domain/value-objects/SearchScope";
import { FakeRagGateway } from "../../fakes/FakeRagGateway";
import { FakeSettingsRepository } from "../../fakes/FakeSettingsRepository";

describe("AskQuestion", () => {
  it("appends answer with sources and insufficient-context flag", async () => {
    const rag = new FakeRagGateway();
    rag.stubChat("answer", [SourceReference.create("a.md", "H1")], true);
    const useCase = new AskQuestion(
      rag,
      new FakeSettingsRepository({ ...DEFAULT_PLUGIN_SETTINGS, vaultId: "vault-a1" }),
    );
    const result = await useCase.execute(
      ChatSession.empty("s1"),
      "What is Prometheus?",
      SearchScope.entireVault(),
    );
    expect(result.kind).toBe("ok");
    if (result.kind === "ok") {
      expect(result.session.messages).toHaveLength(2);
      const assistant = result.session.messages[1];
      expect(assistant?.kind).toBe("assistant");
      if (assistant?.kind === "assistant") {
        expect(assistant.state).toBe("complete");
        expect(assistant.insufficientContext).toBe(true);
        expect(assistant.sources).toHaveLength(1);
      }
    }
  });

  it("marks assistant message cancelled on abort", async () => {
    const rag = new FakeRagGateway();
    rag.chatDelayMs = 50;
    const useCase = new AskQuestion(
      rag,
      new FakeSettingsRepository({ ...DEFAULT_PLUGIN_SETTINGS, vaultId: "vault-a1" }),
    );
    const controller = new AbortController();
    const pending = useCase.execute(
      ChatSession.empty("s1"),
      "What is Prometheus?",
      SearchScope.entireVault(),
      controller.signal,
    );
    controller.abort();
    const result = await pending;
    expect(result.kind).toBe("aborted");
    if (result.kind === "aborted") {
      const assistant = result.session.messages[1];
      expect(assistant?.kind).toBe("assistant");
      if (assistant?.kind === "assistant") {
        expect(assistant.state).toBe("cancelled");
      }
    }
  });
});
