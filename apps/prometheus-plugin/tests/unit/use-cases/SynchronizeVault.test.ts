import { describe, expect, it } from "vitest";

import { DocumentSyncState } from "../../../src/application/services/DocumentSyncState";
import { SynchronizeVault } from "../../../src/application/use-cases/SynchronizeVault";
import { DEFAULT_PLUGIN_SETTINGS } from "../../../src/application/dto/settings";
import { FakeClock } from "../../fakes/FakeClock";
import { FakeNotifier } from "../../fakes/FakeNotifier";
import { FakeRagGateway } from "../../fakes/FakeRagGateway";
import { FakeSettingsRepository } from "../../fakes/FakeSettingsRepository";
import { FakeVaultGateway } from "../../fakes/FakeVaultGateway";

describe("SynchronizeVault", () => {
  it("excludes ignored folders, upserts changed files, and reconciles via syncComplete", async () => {
    const vault = new FakeVaultGateway();
    vault.seed("notes/a.md", "alpha");
    vault.seed("Templates/x.md", "ignored");
    vault.seed("notes/b.md", "beta");

    const rag = new FakeRagGateway();
    const useCase = new SynchronizeVault(
      vault,
      rag,
      new FakeSettingsRepository({
        ...DEFAULT_PLUGIN_SETTINGS,
        vaultId: "vault-a1",
      }),
      new DocumentSyncState(),
      new FakeNotifier(),
      new FakeClock(),
    );

    const result = await useCase.execute();
    expect(result.job.status).toBe("completed");
    expect(rag.lastSyncEntries.map((e) => e.path.value).sort()).toEqual([
      "notes/a.md",
      "notes/b.md",
    ]);
    expect(rag.upsertCalls).toBe(2);
  });

  it("continues after a single-file upsert failure", async () => {
    const vault = new FakeVaultGateway();
    vault.seed("notes/ok.md", "ok");
    vault.seed("notes/bad.md", "bad");
    const rag = new FakeRagGateway();
    rag.upsertShouldFailPaths.add("notes/bad.md");
    const notifier = new FakeNotifier();
    const useCase = new SynchronizeVault(
      vault,
      rag,
      new FakeSettingsRepository({ ...DEFAULT_PLUGIN_SETTINGS, vaultId: "vault-a1" }),
      new DocumentSyncState(),
      notifier,
      new FakeClock(),
    );

    const result = await useCase.execute();
    expect(result.failures).toHaveLength(1);
    expect(result.failures[0]?.path).toBe("notes/bad.md");
    expect(rag.upsertCalls).toBe(2);
    expect(notifier.records.some((r) => r.level === "warning")).toBe(true);
  });

  it("cancel stops the active syncComplete job on the runtime", async () => {
    const vault = new FakeVaultGateway();
    vault.seed("notes/a.md", "alpha");
    const rag = new FakeRagGateway();
    rag.holdJobsPending = true;
    const clock = new FakeClock();
    const useCase = new SynchronizeVault(
      vault,
      rag,
      new FakeSettingsRepository({ ...DEFAULT_PLUGIN_SETTINGS, vaultId: "vault-a1" }),
      new DocumentSyncState(),
      new FakeNotifier(),
      clock,
    );

    let resolveStarted = (_value: undefined): void => undefined;
    const started = new Promise<void>((resolve) => {
      resolveStarted = resolve;
    });

    const syncPromise = useCase.execute(undefined, {
      onJobUpdate: () => {
        resolveStarted(undefined);
      },
    });

    await started;
    const cancelled = await useCase.cancel();
    expect(cancelled?.status).toBe("cancelled");
    clock.advance(250);
    await Promise.resolve();
    const result = await syncPromise;
    expect(result.job.status).toBe("cancelled");
  });
});
