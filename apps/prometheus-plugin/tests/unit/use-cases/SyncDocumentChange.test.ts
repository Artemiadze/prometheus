import { afterEach, describe, expect, it, vi } from "vitest";

import { DocumentSyncState } from "../../../src/application/services/DocumentSyncState";
import { SyncDocumentChange } from "../../../src/application/use-cases/SyncDocumentChange";
import { DEFAULT_PLUGIN_SETTINGS } from "../../../src/application/dto/settings";
import { DocumentId } from "../../../src/domain/value-objects/DocumentId";
import { NotePath } from "../../../src/domain/value-objects/NotePath";
import { FakeNotifier } from "../../fakes/FakeNotifier";
import { FakeRagGateway } from "../../fakes/FakeRagGateway";
import { FakeSettingsRepository } from "../../fakes/FakeSettingsRepository";
import { FakeVaultGateway } from "../../fakes/FakeVaultGateway";

afterEach(() => {
  vi.useRealTimers();
});

describe("SyncDocumentChange", () => {
  function setup() {
    const vault = new FakeVaultGateway();
    const rag = new FakeRagGateway();
    const syncState = new DocumentSyncState();
    const notifier = new FakeNotifier();
    const useCase = new SyncDocumentChange(
      vault,
      rag,
      new FakeSettingsRepository({ ...DEFAULT_PLUGIN_SETTINGS, vaultId: "vault-a1" }),
      syncState,
      notifier,
    );
    return { vault, rag, syncState, notifier, useCase };
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

  it("renames by deleting the old path id and upserting the new path id", async () => {
    const { vault, rag, syncState, useCase } = setup();
    vault.seed("old.md", "body");
    const oldPath = NotePath.create("old.md");
    await useCase.execute({ type: "create", path: oldPath });
    expect(rag.upsertCalls).toBe(1);
    const oldId = DocumentId.fromNotePath(oldPath);
    expect(syncState.getByPath(oldPath)?.documentId.value).toBe(oldId.value);

    const newPath = NotePath.create("new.md");
    vault.seed("new.md", "body");
    await useCase.execute({
      type: "rename",
      path: newPath,
      previousPath: oldPath,
    });
    expect(rag.deleteCalls).toBe(1);
    expect(rag.upsertCalls).toBe(2);
    expect(syncState.getByPath(newPath)?.documentId.value).toBe(
      DocumentId.fromNotePath(newPath).value,
    );
    expect(syncState.getByPath(oldPath)).toBeNull();
    expect(syncState.getByPath(newPath)?.revision).toBeGreaterThan(1);

    await useCase.execute({ type: "delete", path: newPath });
    expect(rag.deleteCalls).toBe(2);
  });

  it("deletes via fromNotePath when syncState has no record", async () => {
    const { rag, syncState, useCase } = setup();
    const path = NotePath.create("orphan.md");
    expect(syncState.getByPath(path)).toBeNull();

    await useCase.execute({ type: "delete", path });

    expect(rag.deleteCalls).toBe(1);
    expect(rag.lastDeletedDocumentIds).toEqual([DocumentId.fromNotePath(path).value]);
  });

  it("delete then create of the same path uses a growing revision", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-03-15T12:00:00.000Z"));
    const { vault, rag, syncState, useCase } = setup();
    const path = NotePath.create("cycle.md");
    vault.seed("cycle.md", "v1");
    await useCase.execute({ type: "create", path });
    const firstRevision = syncState.getByPath(path)?.revision;
    expect(firstRevision).toBe(Date.now());

    await useCase.execute({ type: "delete", path });
    expect(syncState.getByPath(path)).toBeNull();
    expect(rag.deleteCalls).toBe(1);

    vi.advanceTimersByTime(5);
    vault.seed("cycle.md", "v2");
    await useCase.execute({ type: "create", path });
    const secondRevision = syncState.getByPath(path)?.revision;
    expect(secondRevision).toBeGreaterThan(firstRevision ?? 0);
    expect(rag.upsertCalls).toBe(2);
  });

  it("includes the failure reason in the warning", async () => {
    const { vault, rag, notifier, useCase } = setup();
    vault.seed("bad.md", "x");
    rag.upsertShouldFailPaths.add("bad.md");
    await useCase.execute({ type: "create", path: NotePath.create("bad.md") });
    expect(
      notifier.records.some((r) => r.level === "warning" && r.message.includes("bad.md")),
    ).toBe(true);
    expect(notifier.records[0]?.message).toMatch(/Failed to sync bad\.md: /);
  });

  it("skips create/modify into ignored folders", async () => {
    const { vault, rag, useCase } = setup();
    vault.seed("Templates/x.md", "ignored");
    await useCase.execute({ type: "create", path: NotePath.create("Templates/x.md") });
    expect(rag.upsertCalls).toBe(0);
  });
});
