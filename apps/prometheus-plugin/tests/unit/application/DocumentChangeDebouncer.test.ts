import { describe, expect, it } from "vitest";

import { DEFAULT_PLUGIN_SETTINGS } from "../../../src/application/dto/settings";
import { DocumentChangeDebouncer } from "../../../src/application/services/DocumentChangeDebouncer";
import { DocumentSyncState } from "../../../src/application/services/DocumentSyncState";
import { SyncDocumentChange } from "../../../src/application/use-cases/SyncDocumentChange";
import { NotePath } from "../../../src/domain/value-objects/NotePath";
import { FakeClock } from "../../fakes/FakeClock";
import { FakeNotifier } from "../../fakes/FakeNotifier";
import { FakeRagGateway } from "../../fakes/FakeRagGateway";
import { FakeSettingsRepository } from "../../fakes/FakeSettingsRepository";
import { FakeVaultGateway } from "../../fakes/FakeVaultGateway";

describe("DocumentChangeDebouncer", () => {
  function setup(opts?: { debounceMs?: number; maxConcurrent?: number }) {
    const vault = new FakeVaultGateway();
    const rag = new FakeRagGateway();
    const clock = new FakeClock();
    const sync = new SyncDocumentChange(
      vault,
      rag,
      new FakeSettingsRepository({ ...DEFAULT_PLUGIN_SETTINGS, vaultId: "vault-a1" }),
      new DocumentSyncState(),
      new FakeNotifier(),
    );
    const debouncer = new DocumentChangeDebouncer(sync, clock, {
      debounceMs: opts?.debounceMs ?? 100,
      maxConcurrent: opts?.maxConcurrent ?? 2,
    });
    return { vault, rag, clock, debouncer };
  }

  it("coalesces rapid modifies on the same path", async () => {
    const { vault, rag, clock, debouncer } = setup();
    vault.seed("a.md", "v1");
    const path = NotePath.create("a.md");
    debouncer.enqueue({ type: "modify", path });
    vault.seed("a.md", "v2");
    debouncer.enqueue({ type: "modify", path });
    clock.advance(100);
    await debouncer.flush();
    expect(rag.upsertCalls).toBe(1);
  });

  it("rename cancels pending modify on the old path", async () => {
    const { vault, rag, clock, debouncer } = setup();
    vault.seed("old.md", "body");
    vault.seed("new.md", "body");
    debouncer.enqueue({ type: "modify", path: NotePath.create("old.md") });
    debouncer.enqueue({
      type: "rename",
      path: NotePath.create("new.md"),
      previousPath: NotePath.create("old.md"),
    });
    clock.advance(100);
    await debouncer.flush();
    expect(rag.upsertCalls).toBe(1);
  });

  it("caps concurrent syncs", async () => {
    const clock = new FakeClock();
    let inFlight = 0;
    let maxInFlight = 0;
    const releaseGates: Array<() => void> = [];

    const slowSync = {
      execute: async () => {
        inFlight += 1;
        maxInFlight = Math.max(maxInFlight, inFlight);
        await new Promise<void>((resolve) => {
          releaseGates.push(() => {
            inFlight -= 1;
            resolve();
          });
        });
      },
    };

    const debouncer = new DocumentChangeDebouncer(slowSync, clock, {
      debounceMs: 10,
      maxConcurrent: 2,
    });

    for (let i = 0; i < 4; i += 1) {
      debouncer.enqueue({ type: "modify", path: NotePath.create(`f${i}.md`) });
    }
    clock.advance(10);
    await waitUntil(() => inFlight === 2 && releaseGates.length === 2);
    expect(maxInFlight).toBe(2);

    releaseGates.splice(0).forEach((r) => r());
    await waitUntil(() => inFlight === 2 && releaseGates.length === 2);
    releaseGates.splice(0).forEach((r) => r());
    await debouncer.flush();
    expect(maxInFlight).toBe(2);
    expect(inFlight).toBe(0);
  });
});

async function waitUntil(predicate: () => boolean, attempts = 50): Promise<void> {
  for (let i = 0; i < attempts; i += 1) {
    if (predicate()) {
      return;
    }
    await Promise.resolve();
  }
  throw new Error("waitUntil timed out");
}
