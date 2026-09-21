import { describe, expect, it } from "vitest";

import { StartRuntime } from "../../../src/application/use-cases/StartRuntime";
import { RuntimeSessionRegistry } from "../../../src/application/services/RuntimeSessionRegistry";
import { DEFAULT_PLUGIN_SETTINGS } from "../../../src/application/dto/settings";
import { FakeClock } from "../../fakes/FakeClock";
import { FakeRagGateway } from "../../fakes/FakeRagGateway";
import { FakeRuntimeGateway } from "../../fakes/FakeRuntimeGateway";
import { FakeSettingsRepository } from "../../fakes/FakeSettingsRepository";

describe("StartRuntime", () => {
  it("skips spawn when health is already available", async () => {
    const runtime = new FakeRuntimeGateway();
    runtime.setLocateResult("managed", "0.1.0");
    const rag = new FakeRagGateway();
    const useCase = new StartRuntime(
      runtime,
      rag,
      new FakeSettingsRepository(),
      new RuntimeSessionRegistry(),
      new FakeClock(),
    );

    const result = await useCase.execute();
    expect(result.kind).toBe("ready");
    if (result.kind === "ready") {
      expect(result.spawned).toBe(false);
      expect(result.ownership).toBe("external");
    }
    expect(runtime.startCalls).toBe(0);
  });

  it("returns missing without throwing when binary is absent", async () => {
    const runtime = new FakeRuntimeGateway();
    const rag = new FakeRagGateway();
    rag.healthResult = null;
    const useCase = new StartRuntime(
      runtime,
      rag,
      new FakeSettingsRepository(),
      new RuntimeSessionRegistry(),
      new FakeClock(),
    );

    const result = await useCase.execute();
    expect(result).toEqual({
      kind: "missing",
      runtime: { kind: "missing" },
      spawned: false,
    });
  });

  it("spawns and waits for health without exposing the session token in the result payload", async () => {
    const runtime = new FakeRuntimeGateway();
    runtime.setLocateResult("managed", "0.1.0");
    const rag = new FakeRagGateway();
    rag.healthFailCount = 1;
    const sessions = new RuntimeSessionRegistry();
    const useCase = new StartRuntime(
      runtime,
      rag,
      new FakeSettingsRepository({ ...DEFAULT_PLUGIN_SETTINGS }),
      sessions,
      new FakeClock(),
    );

    const result = await useCase.execute();
    expect(result.kind).toBe("ready");
    if (result.kind === "ready") {
      expect(result.spawned).toBe(true);
      expect(result.ownership).toBe("owned");
      expect(result.connection.sessionToken).toBe("test-session-token");
    }
    expect(runtime.startCalls).toBe(1);
    expect(sessions.isOwned()).toBe(true);
  });
});
