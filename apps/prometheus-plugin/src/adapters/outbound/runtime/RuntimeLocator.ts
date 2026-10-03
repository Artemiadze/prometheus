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

const DEFAULT_VERSION_PROBE_MS = 3_000;

export class RuntimeLocator {
  private readonly spawnProcess: typeof spawn;
  private readonly versionProbeTimeoutMs: number;
  private versionCache: { readonly path: string; readonly version: string | null } | null = null;

  constructor(private readonly deps: RuntimeLocatorDeps) {
    this.spawnProcess = deps.spawnProcess ?? spawn;
    this.versionProbeTimeoutMs = deps.versionProbeTimeoutMs ?? DEFAULT_VERSION_PROBE_MS;
  }

  /**
   * Fast presence check only. Do not spawn `--version` here: Status polls locate()
   * frequently, and frozen binaries can hang probes and leave orphan processes.
   */
  async locate(): Promise<RuntimeLocateResult> {
    const settings = await this.deps.getSettings();
    const customPath = settings.customBinaryPath?.trim() ?? "";
    if (customPath.length > 0 && (await this.isExecutable(customPath))) {
      return {
        kind: "custom",
        version: this.versionCache?.path === customPath ? this.versionCache.version : null,
      };
    }

    const managedPath = this.managedInstallPath();
    if (await this.isExecutable(managedPath)) {
      return {
        kind: "managed",
        version: this.versionCache?.path === managedPath ? this.versionCache.version : null,
      };
    }

    return { kind: "missing", version: null };
  }

  async resolveBinaryPath(): Promise<string | null> {
    const settings = await this.deps.getSettings();
    const customPath = settings.customBinaryPath?.trim() ?? "";
    if (customPath.length > 0 && (await this.isExecutable(customPath))) {
      return customPath;
    }
    const managedPath = this.managedInstallPath();
    if (await this.isExecutable(managedPath)) {
      return managedPath;
    }
    return null;
  }

  async getInstalledVersion(): Promise<string | null> {
    const binary = await this.resolveBinaryPath();
    if (!binary) {
      return null;
    }
    if (this.versionCache?.path === binary) {
      return this.versionCache.version;
    }
    const version = await this.probeVersion(binary);
    this.versionCache = { path: binary, version };
    return version;
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
      let settled = false;
      const finish = (value: string | null): void => {
        if (settled) {
          return;
        }
        settled = true;
        resolve(value);
      };

      const child = this.spawnProcess(binaryPath, ["--version"], {
        stdio: ["ignore", "pipe", "ignore"],
        windowsHide: true,
        // Own process group so timeout can kill the whole PyInstaller tree.
        detached: process.platform !== "win32",
      });
      let stdout = "";
      child.stdout?.on("data", (chunk: Buffer | string) => {
        stdout += String(chunk);
      });

      const timer = setTimeout(() => {
        killProbe(child.pid);
        finish(null);
      }, this.versionProbeTimeoutMs);

      child.on("error", () => {
        clearTimeout(timer);
        finish(null);
      });
      child.on("close", () => {
        clearTimeout(timer);
        const line = stdout.trim().split(/\r?\n/)[0]?.trim() ?? "";
        finish(line.length > 0 ? line : null);
      });
    });
  }
}

function killProbe(pid: number | undefined): void {
  if (pid === undefined) {
    return;
  }
  try {
    if (process.platform === "win32") {
      process.kill(pid);
      return;
    }
    // Negative PID kills the process group started with detached: true.
    process.kill(-pid, "SIGKILL");
  } catch {
    try {
      process.kill(pid, "SIGKILL");
    } catch {
      /* already gone */
    }
  }
}
