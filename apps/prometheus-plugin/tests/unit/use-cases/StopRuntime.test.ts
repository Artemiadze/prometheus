import { describe, expect, it } from "vitest";

import { RuntimeSessionRegistry } from "../../../src/application/services/RuntimeSessionRegistry";
import { StopRuntime } from "../../../src/application/use-cases/StopRuntime";
import { FakeClock } from "../../fakes/FakeClock";
import { FakeRuntimeGateway } from "../../fakes/FakeRuntimeGateway";

describe("StopRuntime", () => {
  it("does not stop an external session", async () => {
    const runtime = new FakeRuntimeGateway();
    const sessions = new RuntimeSessionRegistry();
    sessions.set({
      connection: { baseUrl: "http://127.0.0.1:1", sessionToken: "x" },
      ownership: "external",
    });
    const useCase = new StopRuntime(runtime, sessions, new FakeClock());
    const result = await useCase.execute();
    expect(result.stopped).toBe(false);
    expect(runtime.stopCalls).toEqual([]);
  });

  it("stops an owned session gracefully", async () => {
    const runtime = new FakeRuntimeGateway();
    const sessions = new RuntimeSessionRegistry();
    sessions.set({
      connection: { baseUrl: "http://127.0.0.1:1", sessionToken: "x" },
      ownership: "owned",
    });
    const useCase = new StopRuntime(runtime, sessions, new FakeClock());
    const result = await useCase.execute();
    expect(result.stopped).toBe(true);
    expect(runtime.stopCalls).toEqual(["graceful"]);
    expect(sessions.get()).toBeNull();
  });

  it("force-stops when graceful stop times out", async () => {
    const runtime = new FakeRuntimeGateway();
    runtime.hangGracefulStop = true;
    const sessions = new RuntimeSessionRegistry();
    sessions.set({
      connection: { baseUrl: "http://127.0.0.1:1", sessionToken: "x" },
      ownership: "owned",
    });
    const clock = new FakeClock();
    const useCase = new StopRuntime(runtime, sessions, clock);
    const pending = useCase.execute(undefined, { gracefulTimeoutMs: 50 });
    clock.advance(50);
    const result = await pending;
    expect(result.stopped).toBe(true);
    expect(runtime.stopCalls).toEqual(["graceful", "force"]);
  });
});
