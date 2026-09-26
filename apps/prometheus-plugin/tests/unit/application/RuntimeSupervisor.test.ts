import { describe, expect, it } from "vitest";

import { RuntimeSupervisor } from "../../../src/application/services/RuntimeSupervisor";
import { RuntimeSessionRegistry } from "../../../src/application/services/RuntimeSessionRegistry";
import type { StartRuntimeResult } from "../../../src/application/use-cases/StartRuntime";
import type { StartRuntime } from "../../../src/application/use-cases/StartRuntime";
import { ManagedRuntimeState } from "../../../src/domain/entities/RuntimeStatus";
import { FakeClock } from "../../fakes/FakeClock";
import { FakeNotifier } from "../../fakes/FakeNotifier";

describe("RuntimeSupervisor", () => {
  it("limits automatic restarts and notifies the user", async () => {
    const sessions = new RuntimeSessionRegistry();
    sessions.set({
      connection: { baseUrl: "http://127.0.0.1:8765", sessionToken: "token" },
      ownership: "owned",
    });
    const clock = new FakeClock();
    const notifier = new FakeNotifier();
    const startRuntime = {
      execute: async (): Promise<StartRuntimeResult> => ({
        kind: "missing",
        runtime: ManagedRuntimeState.missing(),
        spawned: false,
      }),
    } as StartRuntime;
    const supervisor = new RuntimeSupervisor(startRuntime, sessions, clock, notifier, {
      maxRestarts: 2,
      restartBackoffMs: 0,
    });

    supervisor.handleProcessExit("crashed");
    supervisor.handleProcessExit("crashed");
    supervisor.handleProcessExit("crashed");
    await supervisor.flush();

    expect(notifier.records.some((record) => record.level === "warning")).toBe(true);
  });
});
