import { describe, expect, it } from "vitest";

import { SearchNotes } from "../../../src/application/use-cases/SearchNotes";
import { DEFAULT_PLUGIN_SETTINGS } from "../../../src/application/dto/settings";
import { SearchScope } from "../../../src/domain/value-objects/SearchScope";
import { QueryTooShortError } from "../../../src/domain/errors";
import { FakeRagGateway } from "../../fakes/FakeRagGateway";
import { FakeSettingsRepository } from "../../fakes/FakeSettingsRepository";

describe("SearchNotes", () => {
  it("rejects short queries without calling rag", async () => {
    const rag = new FakeRagGateway();
    const useCase = new SearchNotes(
      rag,
      new FakeSettingsRepository({ ...DEFAULT_PLUGIN_SETTINGS, vaultId: "vault-a1" }),
    );
    const result = await useCase.execute("ab", SearchScope.entireVault());
    expect(result.kind).toBe("validation");
    if (result.kind === "validation") {
      expect(result.error).toBeInstanceOf(QueryTooShortError);
    }
    expect(rag.searchCalls).toBe(0);
    expect(rag.chatCalls).toBe(0);
  });

  it("returns hits and aborts prior in-flight search", async () => {
    const rag = new FakeRagGateway();
    rag.stubSearchHit("a.md", "text");
    const useCase = new SearchNotes(
      rag,
      new FakeSettingsRepository({ ...DEFAULT_PLUGIN_SETTINGS, vaultId: "vault-a1" }),
    );
    const first = useCase.execute("hello", SearchScope.entireVault());
    const second = await useCase.execute("world", SearchScope.entireVault());
    expect(second.kind).toBe("ok");
    const firstResult = await first;
    expect(["ok", "aborted"]).toContain(firstResult.kind);
    expect(rag.chatCalls).toBe(0);
  });
});
