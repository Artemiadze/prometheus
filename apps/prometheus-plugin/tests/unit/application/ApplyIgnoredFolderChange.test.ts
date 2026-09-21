import { describe, expect, it } from "vitest";

import { DEFAULT_PLUGIN_SETTINGS } from "../../../src/application/dto/settings";
import { ApplyIgnoredFolderChange } from "../../../src/application/services/ApplyIgnoredFolderChange";
import { computeContentHash } from "../../../src/application/services/contentHash";
import { DocumentSyncState } from "../../../src/application/services/DocumentSyncState";
import {
  effectiveIgnoredFolders,
  isIgnoredPath,
} from "../../../src/application/services/settingsHelpers";
import { DocumentId } from "../../../src/domain/value-objects/DocumentId";
import { NotePath } from "../../../src/domain/value-objects/NotePath";
import { FakeNotifier } from "../../fakes/FakeNotifier";
import { FakeRagGateway } from "../../fakes/FakeRagGateway";
import { FakeSettingsRepository } from "../../fakes/FakeSettingsRepository";

describe("effectiveIgnoredFolders / isIgnoredPath", () => {
  it("always includes .obsidian/", () => {
    const folders = effectiveIgnoredFolders({
      ...DEFAULT_PLUGIN_SETTINGS,
      ignoredFolders: ["Templates/"],
    });
    expect(folders).toContain(".obsidian/");
    expect(folders).toContain("Templates/");
    expect(isIgnoredPath(".obsidian/config", folders)).toBe(true);
    expect(isIgnoredPath("Templates/x.md", folders)).toBe(true);
    expect(isIgnoredPath("notes/a.md", folders)).toBe(false);
  });
});

describe("ApplyIgnoredFolderChange", () => {
  it("deletes documents that fall under newly ignored prefixes", async () => {
    const syncState = new DocumentSyncState();
    const keep = NotePath.create("notes/a.md");
    const drop = NotePath.create("Archive/old.md");
    syncState.upsert({
      documentId: DocumentId.fromNotePath(keep),
      path: keep,
      contentHash: computeContentHash("a"),
      revision: 1,
    });
    syncState.upsert({
      documentId: DocumentId.fromNotePath(drop),
      path: drop,
      contentHash: computeContentHash("b"),
      revision: 1,
    });

    const rag = new FakeRagGateway();
    const useCase = new ApplyIgnoredFolderChange(
      rag,
      new FakeSettingsRepository({ ...DEFAULT_PLUGIN_SETTINGS, vaultId: "vault-a1" }),
      syncState,
      new FakeNotifier(),
    );

    const removed = await useCase.execute({
      previousIgnoredFolders: [],
      nextIgnoredFolders: ["Archive/"],
    });
    expect(removed).toBe(1);
    expect(rag.deleteCalls).toBe(1);
    expect(syncState.getByPath(drop)).toBeNull();
    expect(syncState.getByPath(keep)).not.toBeNull();
  });
});
