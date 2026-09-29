import { describe, expect, it, vi } from "vitest";

import { SearchStore } from "../../../../../src/adapters/inbound/obsidian/search/SearchStore";
import { DEFAULT_PLUGIN_SETTINGS } from "../../../../../src/application/dto/settings";
import type { SearchHitDto } from "../../../../../src/application/dto/rag";
import type { Unsubscribe } from "../../../../../src/application/dto/vault";
import { NotePath } from "../../../../../src/domain/value-objects/NotePath";
import { FakeClock } from "../../../../fakes/FakeClock";
import { FakeSettingsRepository } from "../../../../fakes/FakeSettingsRepository";

function createVaultStub() {
  return {
    getActiveNotePath: () => null,
    getActiveFolderPath: () => null,
    subscribeActiveFile:
      (_listener: (path: NotePath | null) => void): Unsubscribe =>
      () =>
        undefined,
  };
}

/**
 * PLG-85 — SearchStore UI states without Obsidian DOM.
 * Covers idle, loading (searching), error, empty, and success (results).
 */
describe("SearchStore UI states (PLG-85)", () => {
  it("starts idle", async () => {
    const store = new SearchStore({
      searchNotes: { execute: vi.fn() },
      ensureRuntime: async () => ({ ok: true }),
      openSource: async () => undefined,
      settings: new FakeSettingsRepository({ ...DEFAULT_PLUGIN_SETTINGS, vaultId: "vault-a1" }),
      vault: createVaultStub(),
      clock: new FakeClock(),
      debounceMs: 0,
    });
    await Promise.resolve();
    expect(store.getState().status).toBe("idle");
    expect(store.getState().hits).toEqual([]);
    store.dispose();
  });

  it("enters searching then results (success)", async () => {
    let resolveHits = (_hits: readonly SearchHitDto[]): void => undefined;
    const searchNotes = {
      execute: vi.fn(async () => ({
        kind: "ok" as const,
        hits: await new Promise<readonly SearchHitDto[]>((resolve) => {
          resolveHits = resolve;
        }),
      })),
    };
    const store = new SearchStore({
      searchNotes,
      ensureRuntime: async () => ({ ok: true }),
      openSource: async () => undefined,
      settings: new FakeSettingsRepository({ ...DEFAULT_PLUGIN_SETTINGS, vaultId: "vault-a1" }),
      vault: createVaultStub(),
      clock: new FakeClock(),
      debounceMs: 0,
    });

    const seen: string[] = [];
    store.subscribe((state) => {
      if (seen[seen.length - 1] !== state.status) {
        seen.push(state.status);
      }
    });

    const pending = store.setQuery("prometheus");
    await vi.waitFor(() => {
      expect(store.getState().status).toBe("searching");
    });

    resolveHits([
      {
        path: NotePath.create("notes/a.md"),
        heading: null,
        text: "hit",
        score: 1,
      },
    ]);
    await pending;
    expect(store.getState().status).toBe("results");
    expect(store.getState().hits).toHaveLength(1);
    expect(seen).toContain("searching");
    expect(seen).toContain("results");
    store.dispose();
  });

  it("maps zero hits to empty", async () => {
    const store = new SearchStore({
      searchNotes: {
        execute: async () => ({ kind: "ok" as const, hits: [] }),
      },
      ensureRuntime: async () => ({ ok: true }),
      openSource: async () => undefined,
      settings: new FakeSettingsRepository({ ...DEFAULT_PLUGIN_SETTINGS, vaultId: "vault-a1" }),
      vault: createVaultStub(),
      clock: new FakeClock(),
      debounceMs: 0,
    });
    await store.setQuery("nothing matches");
    expect(store.getState().status).toBe("empty");
    expect(store.getState().hits).toEqual([]);
    store.dispose();
  });

  it("maps ensureRuntime failure to error", async () => {
    const store = new SearchStore({
      searchNotes: { execute: vi.fn() },
      ensureRuntime: async () => ({ ok: false, message: "Runtime down" }),
      openSource: async () => undefined,
      settings: new FakeSettingsRepository({ ...DEFAULT_PLUGIN_SETTINGS, vaultId: "vault-a1" }),
      vault: createVaultStub(),
      clock: new FakeClock(),
      debounceMs: 0,
    });
    await store.setQuery("hello");
    expect(store.getState().status).toBe("error");
    expect(store.getState().errorMessage).toBe("Runtime down");
    store.dispose();
  });
});
