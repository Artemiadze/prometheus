import { describe, expect, it } from "vitest";

import { DocumentSyncState } from "../../../src/application/services/DocumentSyncState";
import { SyncDocumentChange } from "../../../src/application/use-cases/SyncDocumentChange";
import { DEFAULT_PLUGIN_SETTINGS } from "../../../src/application/dto/settings";
import { DocumentId } from "../../../src/domain/value-objects/DocumentId";
import { NotePath } from "../../../src/domain/value-objects/NotePath";
import { FakeNotifier } from "../../fakes/FakeNotifier";
import { FakeRagGateway } from "../../fakes/FakeRagGateway";
import { FakeSettingsRepository } from "../../fakes/FakeSettingsRepository";
import { FakeVaultGateway } from "../../fakes/FakeVaultGateway";

describe("SyncDocumentChange", () => {
  function setup() {
    const vault = new FakeVaultGateway();
    const rag = new FakeRagGateway();
    const syncState = new DocumentSyncState();
    const useCase = new SyncDocumentChange(
      vault,
      rag,
      new FakeSettingsRepository({ ...DEFAULT_PLUGIN_SETTINGS, vaultId: "vault-a1" }),
      syncState,
      new FakeNotifier(),
    );
    return { vault, rag, syncState, useCase };
  }

  it("skips unchanged content", async () => {
    const { vault, rag, syncState, useCase } = setup();
    vault.seed("a.md", "same");
    const path = NotePath.create("a.md");
    const documentId = DocumentId.fromNotePath(path);
    const { computeContentHash } = await import("../../../src/application/services/contentHash");
    syncState.upsert({
      documentId,
      path,
      contentHash: computeContentHash("same"),
      revision: 1,
    });
    await useCase.execute({ type: "modify", path });
    expect(rag.upsertCalls).toBe(0);
  });

  it("force-upserts unchanged content when force is true", async () => {
    const { vault, rag, syncState, useCase } = setup();
    vault.seed("a.md", "same");
    const path = NotePath.create("a.md");
    const documentId = DocumentId.fromNotePath(path);
    const { computeContentHash } = await import("../../../src/application/services/contentHash");
    syncState.upsert({
      documentId,
      path,
      contentHash: computeContentHash("same"),
      revision: 1,
    });
    await useCase.execute({ type: "modify", path }, undefined, { force: true });
    expect(rag.upsertCalls).toBe(1);
  });

  it("upserts modified content and deletes/renames with stable ids", async () => {
    const { vault, rag, syncState, useCase } = setup();
    vault.seed("old.md", "body");
    const oldPath = NotePath.create("old.md");
    await useCase.execute({ type: "create", path: oldPath });
    expect(rag.upsertCalls).toBe(1);
    const id = syncState.getByPath(oldPath)?.documentId;
    expect(id).toBeTruthy();

    vault.seed("new.md", "body");
    await useCase.execute({
      type: "rename",
      path: NotePath.create("new.md"),
      previousPath: oldPath,
    });
    expect(syncState.getByPath(NotePath.create("new.md"))?.documentId.value).toBe(id?.value);
    expect(syncState.getByPath(oldPath)).toBeNull();

    await useCase.execute({ type: "delete", path: NotePath.create("new.md") });
    expect(rag.deleteCalls).toBe(1);
  });

  it("skips create/modify into ignored folders", async () => {
    const { vault, rag, useCase } = setup();
    vault.seed("Templates/x.md", "ignored");
    await useCase.execute({ type: "create", path: NotePath.create("Templates/x.md") });
    expect(rag.upsertCalls).toBe(0);
  });
});
