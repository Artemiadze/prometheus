import { describe, expect, it } from "vitest";

import { GetSystemStatus } from "../../../src/application/use-cases/GetSystemStatus";
import { DEFAULT_PLUGIN_SETTINGS } from "../../../src/application/dto/settings";
import { ManagedRuntimeState } from "../../../src/domain/entities/RuntimeStatus";
import { FakeClock } from "../../fakes/FakeClock";
import { FakeRagGateway } from "../../fakes/FakeRagGateway";
import { FakeRuntimeGateway } from "../../fakes/FakeRuntimeGateway";
import { FakeSettingsRepository } from "../../fakes/FakeSettingsRepository";

describe("GetSystemStatus", () => {
  it("returns degraded status when runtime API is unavailable", async () => {
    const rag = new FakeRagGateway();
    rag.status = async () => {
      throw new Error("down");
    };
    const runtime = new FakeRuntimeGateway();
    runtime.setLocateResult("managed", "0.1.0");
    await runtime.start();
    const useCase = new GetSystemStatus(
      rag,
      runtime,
      new FakeSettingsRepository(),
      new FakeClock(),
    );
    const status = await useCase.execute();
    expect(status.service).toBeNull();
    expect(status.index.kind).toBe("notIndexed");
    expect(status.runtime.runtime.kind).toBe("running");
  });

  it("maps rebuild_required and throttles polls", async () => {
    const rag = new FakeRagGateway();
    rag.serviceStatus = {
      ...rag.serviceStatus,
      indexState: "rebuild_required",
      reindexRequired: true,
      reindexReason: "embedding changed",
    };
    const runtime = new FakeRuntimeGateway();
    runtime.setLocateResult("managed", "0.1.0");
    await runtime.start();
    expect(runtime.getProcessState()).toEqual(ManagedRuntimeState.running("0.1.0"));
    const clock = new FakeClock(new Date(1_000));
    const useCase = new GetSystemStatus(
      rag,
      runtime,
      new FakeSettingsRepository({ ...DEFAULT_PLUGIN_SETTINGS, llmModel: "qwen3:4b" }),
      clock,
      { minIntervalMs: 1_000 },
    );
    const first = await useCase.execute();
    expect(first.index.kind).toBe("reindexRequired");
    clock.advance(100);
    const second = await useCase.execute();
    expect(second.fetchedAt.getTime()).toBe(first.fetchedAt.getTime());
  });
});
