import { describe, expect, it } from "vitest";

import { DEFAULT_PLUGIN_SETTINGS } from "../../../src/application/dto/settings";
import { InstallRuntime } from "../../../src/application/use-cases/InstallRuntime";
import {
  NetworkAccessDisabledError,
  RuntimeChecksumMismatchError,
} from "../../../src/domain/errors";
import { FakeRuntimeGateway } from "../../fakes/FakeRuntimeGateway";
import { FakeSettingsRepository } from "../../fakes/FakeSettingsRepository";

describe("InstallRuntime", () => {
  it("downloads with progress then verifies", async () => {
    const runtime = new FakeRuntimeGateway();
    const settings = new FakeSettingsRepository();
    const states: string[] = [];
    const useCase = new InstallRuntime(runtime, settings);
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
    const useCase = new InstallRuntime(runtime, new FakeSettingsRepository());
    await expect(useCase.execute()).rejects.toBeInstanceOf(RuntimeChecksumMismatchError);
  });

  it("blocks download when network access is disabled", async () => {
    const runtime = new FakeRuntimeGateway();
    const settings = new FakeSettingsRepository({
      ...DEFAULT_PLUGIN_SETTINGS,
      networkAccess: "disabled",
    });
    const useCase = new InstallRuntime(runtime, settings);
    await expect(useCase.execute()).rejects.toBeInstanceOf(NetworkAccessDisabledError);
    expect(runtime.downloadProgress).toHaveLength(0);
  });

  it("skips download when a managed binary is already installed", async () => {
    const runtime = new FakeRuntimeGateway();
    runtime.setLocateResult("managed", "0.1.0");
    const useCase = new InstallRuntime(runtime, new FakeSettingsRepository());
    const states: string[] = [];
    await useCase.execute((state) => {
      states.push(state.kind);
    });
    expect(runtime.downloadProgress).toHaveLength(0);
    expect(states).toEqual(["verifying"]);
  });
});
