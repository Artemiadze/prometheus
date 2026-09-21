import { describe, expect, it } from "vitest";

import { InstallRuntime } from "../../../src/application/use-cases/InstallRuntime";
import { RuntimeChecksumMismatchError } from "../../../src/domain/errors";
import { FakeRuntimeGateway } from "../../fakes/FakeRuntimeGateway";

describe("InstallRuntime", () => {
  it("downloads with progress then verifies", async () => {
    const runtime = new FakeRuntimeGateway();
    const states: string[] = [];
    const useCase = new InstallRuntime(runtime);
    const result = await useCase.execute((state) => {
      states.push(state.kind);
    });
    expect(result.kind).toBe("verifying");
    expect(states).toContain("downloading");
    expect(states).toContain("verifying");
    expect(runtime.downloadProgress.map((p) => p.percent)).toEqual([25, 50, 75, 100]);
  });

  it("maps checksum failure", async () => {
    const runtime = new FakeRuntimeGateway();
    runtime.verifyShouldFail = true;
    const useCase = new InstallRuntime(runtime);
    await expect(useCase.execute()).rejects.toBeInstanceOf(RuntimeChecksumMismatchError);
  });
});
