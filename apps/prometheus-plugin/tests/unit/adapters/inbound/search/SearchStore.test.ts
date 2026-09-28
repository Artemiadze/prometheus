import { describe, expect, it, vi } from "vitest";

import { SearchStore } from "../../../../../src/adapters/inbound/obsidian/search/SearchStore";
import { DEFAULT_PLUGIN_SETTINGS } from "../../../../../src/application/dto/settings";
import type { SearchHitDto } from "../../../../../src/application/dto/rag";
import type { Unsubscribe } from "../../../../../src/application/dto/vault";
import { SearchNotes } from "../../../../../src/application/use-cases/SearchNotes";
import { NotePath } from "../../../../../src/domain/value-objects/NotePath";
import { FakeClock } from "../../../../fakes/FakeClock";
import { FakeRagGateway } from "../../../../fakes/FakeRagGateway";
import { FakeSettingsRepository } from "../../../../fakes/FakeSettingsRepository";

function createVaultStub(active: NotePath | null = null) {
  let current = active;
  const listeners = new Set<(path: NotePath | null) => void>();
  return {
    getActiveNotePath: () => current,
    getActiveFolderPath: () => current?.parent ?? null,
    subscribeActiveFile: (listener: (path: NotePath | null) => void): Unsubscribe => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    setActive(path: NotePath | null) {
      current = path;
      for (const listener of listeners) {
        listener(path);
      }
    },
  };
}

describe("SearchStore", () => {
  it("debounces rapid queries into a single search", async () => {
    const rag = new FakeRagGateway();
    rag.stubSearchHit("a.md", "hello", 0.9);
    const settings = new FakeSettingsRepository({
      ...DEFAULT_PLUGIN_SETTINGS,
      vaultId: "vault-a1",
    });
    const clock = new FakeClock();
    const store = new SearchStore({
      searchNotes: new SearchNotes(rag, settings),
      ensureRuntime: async () => ({ ok: true }),
      openSource: async () => undefined,
      settings,
      vault: createVaultStub(),
      clock,
      debounceMs: 300,
    });

    const pending = [store.setQuery("abc"), store.setQuery("abcd"), store.setQuery("abcde")];
    await Promise.resolve();
    await Promise.resolve();
    clock.advance(300);
    await Promise.all(pending);

    expect(rag.searchCalls).toBe(1);
    expect(store.getState().status).toBe("results");
    store.dispose();
  });

  it("ignores stale responses after a newer query", async () => {
    let resolveSlow = (_hits: readonly SearchHitDto[]): void => undefined;
    const searchNotes = {
      execute: vi.fn(async (query: string) => {
        if (query === "first query") {
          return {
            kind: "ok" as const,
            hits: await new Promise<readonly SearchHitDto[]>((resolve) => {
              resolveSlow = resolve;
            }),
          };
        }
        return {
          kind: "ok" as const,
          hits: [
            {
              path: NotePath.create("fresh.md"),
              heading: null,
              text: "fresh",
              score: 1,
            },
          ],
        };
      }),
    };
    const clock = new FakeClock();
    const settings = new FakeSettingsRepository({
      ...DEFAULT_PLUGIN_SETTINGS,
      vaultId: "vault-a1",
    });
    const store = new SearchStore({
      searchNotes,
      ensureRuntime: async () => ({ ok: true }),
      openSource: async () => undefined,
      settings,
      vault: createVaultStub(),
      clock,
      debounceMs: 0,
    });

    const first = store.setQuery("first query");
    await Promise.resolve();
    const second = store.setQuery("second query");
    await second;
    resolveSlow([
      {
        path: NotePath.create("stale.md"),
        heading: null,
        text: "stale",
        score: 0.1,
      },
    ]);
    await first;

    expect(store.getState().hits[0]?.path.value).toBe("fresh.md");
    store.dispose();
  });

  it("maps short queries and missing runtime without searching", async () => {
    const rag = new FakeRagGateway();
    const settings = new FakeSettingsRepository({
      ...DEFAULT_PLUGIN_SETTINGS,
      vaultId: "vault-a1",
    });
    const clock = new FakeClock();
    const store = new SearchStore({
      searchNotes: new SearchNotes(rag, settings),
      ensureRuntime: async () => ({ ok: false, message: "Runtime missing" }),
      openSource: async () => undefined,
      settings,
      vault: createVaultStub(),
      clock,
      debounceMs: 0,
    });

    await store.setQuery("no");
    expect(store.getState().status).toBe("tooShort");
    expect(rag.searchCalls).toBe(0);

    await store.setQuery("hello");
    expect(store.getState().status).toBe("error");
    expect(store.getState().errorMessage).toBe("Runtime missing");
    expect(rag.searchCalls).toBe(0);
    store.dispose();
  });

  it("persists scope mode and refreshes availability on active file change", async () => {
    const settings = new FakeSettingsRepository({
      ...DEFAULT_PLUGIN_SETTINGS,
      vaultId: "vault-a1",
    });
    const vault = createVaultStub(NotePath.create("folder/note.md"));
    const store = new SearchStore({
      searchNotes: { execute: vi.fn() },
      ensureRuntime: async () => ({ ok: true }),
      openSource: async () => undefined,
      settings,
      vault,
      clock: new FakeClock(),
      debounceMs: 0,
    });
    await Promise.resolve();

    await store.setScopeMode("current_note");
    expect((await settings.get()).searchScopeMode).toBe("current_note");
    expect(store.getState().scope.selected).toBe("current_note");

    vault.setActive(null);
    await Promise.resolve();
    expect(store.getState().scope.options.find((o) => o.mode === "current_note")?.enabled).toBe(
      false,
    );
    store.dispose();
  });

  it("stops notifications after dispose", async () => {
    const store = new SearchStore({
      searchNotes: { execute: vi.fn() },
      ensureRuntime: async () => ({ ok: true }),
      openSource: async () => undefined,
      settings: new FakeSettingsRepository(),
      vault: createVaultStub(),
      clock: new FakeClock(),
    });
    let count = 0;
    store.subscribe(() => {
      count += 1;
    });
    store.dispose();
    await store.setQuery("hello");
    expect(count).toBe(1);
  });

  it("focusFolder pins scope until the user changes mode manually", async () => {
    const settings = new FakeSettingsRepository({
      ...DEFAULT_PLUGIN_SETTINGS,
      vaultId: "vault-a1",
    });
    const vault = createVaultStub(null);
    const searchNotes = {
      execute: vi.fn(async () => ({
        kind: "ok" as const,
        hits: [
          {
            path: NotePath.create("Projects/a.md"),
            heading: null,
            text: "hit",
            score: 1,
          },
        ],
      })),
    };
    const store = new SearchStore({
      searchNotes,
      ensureRuntime: async () => ({ ok: true }),
      openSource: async () => undefined,
      settings,
      vault,
      clock: new FakeClock(),
      debounceMs: 0,
    });
    await Promise.resolve();

    await store.focusFolder(NotePath.create("Projects"));
    expect(store.getState().scope.selected).toBe("current_folder");
    expect(store.getState().scope.options.find((o) => o.mode === "current_folder")?.enabled).toBe(
      true,
    );

    vault.setActive(NotePath.create("other/note.md"));
    await Promise.resolve();
    expect(store.getState().scope.selected).toBe("current_folder");
    expect(
      store.getState().scope.options.find((o) => o.mode === "current_folder")?.label,
    ).toContain("Projects");

    await store.setQuery("hello");
    expect(searchNotes.execute).toHaveBeenCalledWith(
      "hello",
      expect.objectContaining({
        mode: "current_folder",
        folders: [expect.objectContaining({ value: "Projects" })],
      }),
      expect.anything(),
      expect.anything(),
    );

    await store.setScopeMode("entire_vault");
    expect(store.getState().scope.selected).toBe("entire_vault");
    expect(store.getState().scope.options.find((o) => o.mode === "current_folder")?.label).toBe(
      "Current folder",
    );
    store.dispose();
  });
});
