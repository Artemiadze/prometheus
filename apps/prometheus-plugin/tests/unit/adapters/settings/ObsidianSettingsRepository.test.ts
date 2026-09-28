import { describe, expect, it } from "vitest";

import {
  ObsidianSettingsRepository,
  ensureVaultId,
  generateVaultId,
} from "../../../../src/adapters/outbound/settings/ObsidianSettingsRepository";
import { DEFAULT_PLUGIN_SETTINGS } from "../../../../src/application/dto/settings";
import { VaultId } from "../../../../src/domain/value-objects/VaultId";
import { FakeNotifier } from "../../../fakes/FakeNotifier";
import { FakeSettingsRepository } from "../../../fakes/FakeSettingsRepository";

describe("generateVaultId / ensureVaultId", () => {
  it("generates ids matching VaultId regex and not derived from a path", () => {
    const ids = new Set(Array.from({ length: 20 }, () => generateVaultId()));
    expect(ids.size).toBeGreaterThan(1);
    for (const id of ids) {
      expect(() => VaultId.create(id)).not.toThrow();
      expect(id.startsWith("v")).toBe(true);
      expect(id).not.toContain("/");
      expect(id).not.toContain("MyVault");
    }
  });

  it("ensureVaultId persists once and is stable on repeat", async () => {
    const repo = new FakeSettingsRepository({ ...DEFAULT_PLUGIN_SETTINGS, vaultId: null });
    const first = await ensureVaultId(repo);
    const second = await ensureVaultId(repo);
    expect(first).toBe(second);
    expect((await repo.get()).vaultId).toBe(first);
  });
});

describe("ObsidianSettingsRepository", () => {
  it("merges loadData with defaults and saves round-trip", async () => {
    let stored: unknown = { vaultId: "vault-a1", indexingDebounceMs: 100 };
    const plugin = {
      loadData: async () => stored,
      saveData: async (data: unknown) => {
        stored = data;
      },
    };
    const repo = new ObsidianSettingsRepository(plugin);
    const settings = await repo.get();
    expect(settings.vaultId).toBe("vault-a1");
    expect(settings.indexingDebounceMs).toBe(100);
    expect(settings.maxConcurrentSyncs).toBe(DEFAULT_PLUGIN_SETTINGS.maxConcurrentSyncs);
    expect(settings.ignoredFolders).toEqual(DEFAULT_PLUGIN_SETTINGS.ignoredFolders);
    expect(settings.searchScopeMode).toBe("entire_vault");
    expect(settings.applySearchScopeToChat).toBe(false);
    expect(settings.hasCompletedOnboarding).toBe(false);
    expect(settings.chunkSizeTokens).toBe(700);

    await repo.save({ ...settings, autoIndexing: false });
    expect((stored as { autoIndexing: boolean }).autoIndexing).toBe(false);
  });

  it("notifies once when corrupted values are corrected", async () => {
    const stored: unknown = { runtimeMode: "cloud", indexingDebounceMs: -5 };
    const notifier = new FakeNotifier();
    const plugin = {
      loadData: async () => stored,
      saveData: async () => undefined,
    };
    const repo = new ObsidianSettingsRepository(plugin, notifier);
    await repo.get();
    await repo.get();
    expect(notifier.records.filter((r) => r.level === "warning")).toHaveLength(1);
    expect(notifier.records[0]?.message).toContain("corrected");
  });
});
