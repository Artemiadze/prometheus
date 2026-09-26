import { constants as fsConstants } from "node:fs";
import { spawn } from "node:child_process";

import type { PluginSettings } from "../../../application/dto/settings";
import type { RuntimeLocateResult } from "../../../application/ports/RuntimeGateway";
import { managedBinaryPath, resolveDataRoot, type PlatformPathsInput } from "./paths";

export type FileAccess = (path: string, mode?: number) => Promise<void>;

export type RuntimeLocatorDeps = {
  readonly getSettings: () => Promise<PluginSettings>;
  readonly platformPaths: PlatformPathsInput;
  readonly access: FileAccess;
  readonly spawnProcess?: typeof spawn | undefined;
  readonly versionProbeTimeoutMs?: number;
};

const DEFAULT_VERSION_PROBE_MS = 5_000;

export class RuntimeLocator {
  private readonly spawnProcess: typeof spawn;
  private readonly versionProbeTimeoutMs: number;

  constructor(private readonly deps: RuntimeLocatorDeps) {
    this.spawnProcess = deps.spawnProcess ?? spawn;
    this.versionProbeTimeoutMs = deps.versionProbeTimeoutMs ?? DEFAULT_VERSION_PROBE_MS;
  }

  async locate(): Promise<RuntimeLocateResult> {
    const settings = await this.deps.getSettings();
    const customPath = settings.customBinaryPath?.trim() ?? "";
    if (customPath.length > 0 && (await this.isExecutable(customPath))) {
      const version = await this.probeVersion(customPath);
      return { kind: "custom", version };
    }

    const dataRoot = resolveDataRoot(this.deps.platformPaths);
    const managedPath = managedBinaryPath(dataRoot, this.deps.platformPaths.platform);
    if (await this.isExecutable(managedPath)) {
      const version = await this.probeVersion(managedPath);
      return { kind: "managed", version };
    }

    return { kind: "missing", version: null };
  }

  async resolveBinaryPath(): Promise<string | null> {
    const located = await this.locate();
    if (located.kind === "missing") {
      return null;
    }
    const settings = await this.deps.getSettings();
    const customPath = settings.customBinaryPath?.trim() ?? "";
    if (located.kind === "custom" && customPath.length > 0) {
      return customPath;
    }
    const dataRoot = resolveDataRoot(this.deps.platformPaths);
    return managedBinaryPath(dataRoot, this.deps.platformPaths.platform);
  }

  async getInstalledVersion(): Promise<string | null> {
    const binary = await this.resolveBinaryPath();
    if (!binary) {
      return null;
    }
    return this.probeVersion(binary);
  }

  managedInstallPath(): string {
    const dataRoot = resolveDataRoot(this.deps.platformPaths);
    return managedBinaryPath(dataRoot, this.deps.platformPaths.platform);
  }

  dataRootPath(): string {
    return resolveDataRoot(this.deps.platformPaths);
  }

  private async isExecutable(path: string): Promise<boolean> {
    try {
      await this.deps.access(path, fsConstants.X_OK);
      return true;
    } catch {
      try {
        await this.deps.access(path, fsConstants.F_OK);
        return this.deps.platformPaths.platform === "win32";
      } catch {
        return false;
      }
    }
  }

  private probeVersion(binaryPath: string): Promise<string | null> {
    return new Promise((resolve) => {
      const child = this.spawnProcess(binaryPath, ["--version"], {
        stdio: ["ignore", "pipe", "ignore"],
        windowsHide: true,
      });
      let stdout = "";
      child.stdout?.on("data", (chunk: Buffer | string) => {
        stdout += String(chunk);
      });
      const timer = setTimeout(() => {
        child.kill("SIGKILL");
        resolve(null);
      }, this.versionProbeTimeoutMs);
      child.on("error", () => {
        clearTimeout(timer);
        resolve(null);
      });
      child.on("close", () => {
        clearTimeout(timer);
        const line = stdout.trim().split(/\r?\n/)[0]?.trim() ?? "";
        resolve(line.length > 0 ? line : null);
      });
    });
  }
}
