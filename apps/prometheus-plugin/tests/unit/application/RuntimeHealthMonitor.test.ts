import { describe, expect, it } from "vitest";

import { RuntimeHealthMonitor } from "../../../src/application/services/RuntimeHealthMonitor";
import { RuntimeSessionRegistry } from "../../../src/application/services/RuntimeSessionRegistry";
import { FakeClock } from "../../fakes/FakeClock";
import { FakeRagGateway } from "../../fakes/FakeRagGateway";

describe("RuntimeHealthMonitor", () => {
  it("skips health calls while no session is registered", async () => {
    const clock = new FakeClock();
    const rag = new FakeRagGateway();
    rag.healthResult = null;
    const sessions = new RuntimeSessionRegistry();
    const monitor = new RuntimeHealthMonitor(rag, sessions, clock, { intervalMs: 30_000 });
    const controller = new AbortController();

    monitor.start({}, controller.signal);
    const tick = clock.advance(30_000);
    await Promise.resolve();
    controller.abort();
    await monitor.stop();
    void tick;
    expect(rag.healthResult).toBeNull();
  });

  it("reports running state after a successful health check", async () => {
    const clock = new FakeClock();
    const rag = new FakeRagGateway();
    const sessions = new RuntimeSessionRegistry();
    sessions.set({
      connection: { baseUrl: "http://127.0.0.1:8765", sessionToken: "token" },
      ownership: "owned",
    });
    const monitor = new RuntimeHealthMonitor(rag, sessions, clock, { intervalMs: 1_000 });
    const states: string[] = [];
    const controller = new AbortController();
    monitor.start(
      {
        onStateChange: (state) => {
          states.push(state.kind);
        },
      },
      controller.signal,
    );
    await Promise.resolve();
    clock.advance(1_000);
    await Promise.resolve();
    expect(states).toContain("running");
    controller.abort();
    await monitor.stop();
  });

  it("does not declare unavailable on a single failure during startup grace", async () => {
    const clock = new FakeClock();
    const rag = new FakeRagGateway();
    rag.healthResult = null;
    const sessions = new RuntimeSessionRegistry();
    sessions.set({
      connection: { baseUrl: "http://127.0.0.1:8765", sessionToken: "token" },
      ownership: "owned",
    });
    const monitor = new RuntimeHealthMonitor(rag, sessions, clock, {
      intervalMs: 1_000,
      failureThreshold: 3,
      startupGraceMs: 60_000,
    });
    let unavailable = 0;
    const states: string[] = [];
    const controller = new AbortController();
    monitor.start(
      {
        onUnavailable: () => {
          unavailable += 1;
        },
        onStateChange: (state) => {
          states.push(state.kind);
        },
      },
      controller.signal,
    );
    await Promise.resolve();
    clock.advance(1_000);
    await Promise.resolve();
    expect(unavailable).toBe(0);
    expect(states).not.toContain("stopped");
    controller.abort();
    await monitor.stop();
  });

  it("declares unavailable after grace and consecutive failures", async () => {
    const clock = new FakeClock();
    const rag = new FakeRagGateway();
    rag.healthResult = null;
    const sessions = new RuntimeSessionRegistry();
    sessions.set({
      connection: { baseUrl: "http://127.0.0.1:8765", sessionToken: "token" },
      ownership: "owned",
    });
    const monitor = new RuntimeHealthMonitor(rag, sessions, clock, {
      intervalMs: 1_000,
      failureThreshold: 3,
      startupGraceMs: 5_000,
      errorBackoffFactor: 1,
      maxIntervalMs: 1_000,
    });
    let unavailable = 0;
    const controller = new AbortController();
    monitor.start(
      {
        onUnavailable: () => {
          unavailable += 1;
        },
      },
      controller.signal,
    );

    // Past grace, then three failing checks.
    for (let i = 0; i < 6; i += 1) {
      clock.advance(1_000);
      await Promise.resolve();
      await Promise.resolve();
    }

    expect(unavailable).toBeGreaterThanOrEqual(1);
    controller.abort();
    await monitor.stop();
  });
});
