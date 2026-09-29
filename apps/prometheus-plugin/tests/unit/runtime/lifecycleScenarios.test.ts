import { describe, expect, it, vi } from "vitest";

import { RuntimeSupervisor } from "../../../src/application/services/RuntimeSupervisor";
import { RuntimeSessionRegistry } from "../../../src/application/services/RuntimeSessionRegistry";
import { StartRuntime } from "../../../src/application/use-cases/StartRuntime";
import { StopRuntime } from "../../../src/application/use-cases/StopRuntime";
import { InstallRuntime } from "../../../src/application/use-cases/InstallRuntime";
import {
  RuntimeChecksumMismatchError,
  RuntimeStartFailedError,
  RuntimeVersionIncompatibleError,
} from "../../../src/domain/errors";
import { ManagedRuntimeState } from "../../../src/domain/entities/RuntimeStatus";
import { allocateLoopbackPort } from "../../../src/adapters/outbound/runtime/portAllocator";
import { FakeClock } from "../../fakes/FakeClock";
import { FakeNotifier } from "../../fakes/FakeNotifier";
import { FakeRagGateway } from "../../fakes/FakeRagGateway";
import { FakeRuntimeGateway } from "../../fakes/FakeRuntimeGateway";
import { FakeSettingsRepository } from "../../fakes/FakeSettingsRepository";
import type { StartRuntime as StartRuntimeType } from "../../../src/application/use-cases/StartRuntime";
import type { StartRuntimeResult } from "../../../src/application/use-cases/StartRuntime";

/**
 * PLG-84 — Runtime lifecycle scenarios stay handled (no uncaught throws) and
 * respect ownership / restart limits.
 */
describe("Runtime lifecycle scenarios (PLG-84)", () => {
  it("returns missing when the binary is absent (no throw)", async () => {
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
    await expect(useCase.execute()).resolves.toMatchObject({ kind: "missing", spawned: false });
  });

  it("surfaces checksum mismatch from install without leaving an unhandled rejection", async () => {
    const runtime = new FakeRuntimeGateway();
    runtime.verifyShouldFail = true;
    const useCase = new InstallRuntime(runtime, new FakeSettingsRepository());
    await expect(useCase.execute()).rejects.toBeInstanceOf(RuntimeChecksumMismatchError);
  });

  it("returns incompatible when health reports a version mismatch", async () => {
    const runtime = new FakeRuntimeGateway();
    runtime.setLocateResult("managed", "0.0.9");
    const rag = new FakeRagGateway();
    rag.health = async () => {
      throw new RuntimeVersionIncompatibleError("0.0.9", ">=0.1.0,<0.2.0");
    };
    const useCase = new StartRuntime(
      runtime,
      rag,
      new FakeSettingsRepository(),
      new RuntimeSessionRegistry(),
      new FakeClock(),
    );
    await expect(useCase.execute()).resolves.toMatchObject({
      kind: "incompatible",
      runtime: {
        kind: "incompatible",
        installedVersion: "0.0.9",
      },
    });
  });

  it("stops only owned processes and leaves external sessions alone", async () => {
    const runtime = new FakeRuntimeGateway();
    const sessions = new RuntimeSessionRegistry();
    sessions.set({
      connection: { baseUrl: "http://127.0.0.1:1", sessionToken: "x" },
      ownership: "external",
    });
    const stop = new StopRuntime(runtime, sessions, new FakeClock());
    expect((await stop.execute()).stopped).toBe(false);
    expect(runtime.stopCalls).toEqual([]);

    sessions.set({
      connection: { baseUrl: "http://127.0.0.1:1", sessionToken: "x" },
      ownership: "owned",
    });
    expect((await stop.execute()).stopped).toBe(true);
    expect(runtime.stopCalls).toEqual(["graceful"]);
  });

  it("respects the automatic restart limit after process crash", async () => {
    const sessions = new RuntimeSessionRegistry();
    sessions.set({
      connection: { baseUrl: "http://127.0.0.1:8765", sessionToken: "token" },
      ownership: "owned",
    });
    const clock = new FakeClock();
    const notifier = new FakeNotifier();
    const start = vi.fn(async (): Promise<StartRuntimeResult> => ({
      kind: "ready",
      runtime: ManagedRuntimeState.running("0.1.0"),
      connection: { baseUrl: "http://127.0.0.1:8765", sessionToken: "token" },
      ownership: "owned",
      spawned: true,
    }));
    const supervisor = new RuntimeSupervisor(
      { execute: start } as unknown as StartRuntimeType,
      sessions,
      clock,
      notifier,
      { maxRestarts: 2, restartBackoffMs: 0 },
    );

    supervisor.handleProcessExit("crashed");
    supervisor.handleProcessExit("crashed");
    supervisor.handleProcessExit("crashed");
    await supervisor.flush();

    expect(start).toHaveBeenCalledTimes(2);
    expect(notifier.records.some((record) => record.level === "warning")).toBe(true);
  });

  it("fails allocateLoopbackPort when maxAttempts is zero", async () => {
    await expect(allocateLoopbackPort(0)).rejects.toThrow(/Failed to allocate/);
  });

  it("maps a start failure into a domain error type the UI can present", () => {
    const error = new RuntimeStartFailedError("port unavailable");
    expect(error).toBeInstanceOf(Error);
    expect(error.message.length).toBeGreaterThan(0);
  });
});
