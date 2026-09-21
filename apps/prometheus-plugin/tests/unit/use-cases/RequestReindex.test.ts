import { describe, expect, it } from "vitest";

import { DocumentSyncState } from "../../../src/application/services/DocumentSyncState";
import { RequestReindex } from "../../../src/application/use-cases/RequestReindex";
import { DEFAULT_PLUGIN_SETTINGS } from "../../../src/application/dto/settings";
import { FakeClock } from "../../fakes/FakeClock";
import { FakeRagGateway } from "../../fakes/FakeRagGateway";
import { FakeSettingsRepository } from "../../fakes/FakeSettingsRepository";
import { FakeVaultGateway } from "../../fakes/FakeVaultGateway";

describe("RequestReindex", () => {
  it("starts once and reuses the active job", async () => {
    const vault = new FakeVaultGateway();
    vault.seed("a.md", "one");
    const rag = new FakeRagGateway();
    rag.holdJobsPending = true;
    rag.serviceStatus = {
      ...rag.serviceStatus,
      reindexRequired: true,
      reindexReason: "embedding changed",
    };
    const useCase = new RequestReindex(
      rag,
      vault,
      new FakeSettingsRepository({ ...DEFAULT_PLUGIN_SETTINGS, vaultId: "vault-a1" }),
      new DocumentSyncState(),
      new FakeClock(),
    );

    const first = await useCase.start();
    expect(first.kind).toBe("started");
    expect(first.reindexRequired).toBe(true);
    expect(rag.reindexCalls).toBe(1);

    const second = await useCase.start();
    expect(second.kind).toBe("already_running");
    expect(second.job.jobId).toBe(first.job.jobId);
    expect(rag.reindexCalls).toBe(1);

    const cancelled = await useCase.cancel();
    expect(cancelled?.status).toBe("cancelled");
  });
});
