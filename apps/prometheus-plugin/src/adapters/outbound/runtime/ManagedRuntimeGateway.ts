import { spawn as nodeSpawn } from "node:child_process";
import { access } from "node:fs/promises";
import { arch, homedir, platform } from "node:os";

import type { PluginSettings } from "../../../application/dto/settings";
import type {
  ProgressCallback,
  RuntimeConnection,
  RuntimeGateway,
  RuntimeLocateResult,
  RuntimeStopMode,
} from "../../../application/ports/RuntimeGateway";
import type { SettingsRepository } from "../../../application/ports/SettingsRepository";
import {
  ManagedRuntimeState,
  type ManagedRuntimeState as ManagedRuntimeStateType,
  type RuntimeStopReason,
} from "../../../domain/entities/RuntimeStatus";
import { isAbortError } from "../../../domain/errors";
import { DiagnosticBuffer } from "./DiagnosticBuffer";
import { allocateLoopbackPort } from "./portAllocator";
import { RuntimeDownloader, type FetchFn } from "./RuntimeDownloader";
import { RuntimeLocator } from "./RuntimeLocator";
import { RuntimeProcess, type RuntimeExitHandler } from "./RuntimeProcess";
import { generateSessionToken } from "./sessionToken";

export type ManagedRuntimeGatewayOptions = {
  readonly settings: SettingsRepository;
  readonly fetchFn?: FetchFn | undefined;
  readonly spawnProcess?: typeof nodeSpawn | undefined;
  readonly onProcessExit?: RuntimeExitHandler;
  readonly diagnostics?: DiagnosticBuffer;
};

export class ManagedRuntimeGateway implements RuntimeGateway {
  private readonly diagnostics: DiagnosticBuffer;
  private readonly locator: RuntimeLocator;
  private readonly downloader: RuntimeDownloader;
  private readonly process: RuntimeProcess;
  private state: ManagedRuntimeStateType = ManagedRuntimeState.missing();
  private lastConnection: RuntimeConnection | null = null;

  constructor(options: ManagedRuntimeGatewayOptions) {
    this.diagnostics = options.diagnostics ?? new DiagnosticBuffer();
    const getSettings = async (): Promise<PluginSettings> => options.settings.get();
    this.locator = new RuntimeLocator({
      getSettings,
      platformPaths: { platform: platform(), env: process.env, homedir: homedir() },
      access,
      ...(options.spawnProcess ? { spawnProcess: options.spawnProcess } : {}),
    });
    this.downloader = new RuntimeDownloader({
      locator: this.locator,
      getSettings,
      fetchFn: options.fetchFn ?? fetch,
      platform: platform(),
      arch: arch(),
    });
    this.process = new RuntimeProcess({
      spawnProcess: options.spawnProcess ?? nodeSpawn,
      diagnostics: this.diagnostics,
      onExit: (reason) => {
        this.state = ManagedRuntimeState.stopped(reason);
        options.onProcessExit?.(reason);
      },
    });
  }

  locate(): Promise<RuntimeLocateResult> {
    return this.locator.locate();
  }

  async download(onProgress: ProgressCallback, signal?: AbortSignal): Promise<void> {
    this.state = ManagedRuntimeState.downloading(0);
    const progress: ProgressCallback = (value) => {
      this.state = ManagedRuntimeState.downloading(value.percent);
      onProgress(value);
    };
    await this.downloader.download(progress, signal);
    this.state = ManagedRuntimeState.verifying();
  }

  async verify(signal?: AbortSignal): Promise<void> {
    this.state = ManagedRuntimeState.verifying();
    await this.downloader.verifyInstalledBinary(signal);
    this.state = ManagedRuntimeState.stopped("requested");
  }

  async start(signal?: AbortSignal): Promise<RuntimeConnection> {
    const binary = await this.locator.resolveBinaryPath();
    if (!binary) {
      throw new Error("Runtime binary is missing");
    }

    const dataDir = this.locator.dataRootPath();
    let lastError: Error | undefined;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      throwIfAborted(signal);
      const port = await allocateLoopbackPort();
      const sessionToken = generateSessionToken();
      try {
        await this.process.start({
          binaryPath: binary,
          host: "127.0.0.1",
          port,
          dataDir,
          sessionToken,
          signal,
        });
        this.state = ManagedRuntimeState.starting();
        const version = (await this.locator.getInstalledVersion()) ?? "0.1.0";
        this.process.markRunning(version);
        this.state = ManagedRuntimeState.running(version);
        const connection: RuntimeConnection = {
          baseUrl: `http://127.0.0.1:${port}`,
          sessionToken,
        };
        this.lastConnection = connection;
        return connection;
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));
        if (isAbortError(error)) {
          throw error;
        }
        await this.process.stop("force", signal).catch(() => undefined);
        if (this.process.getProcessState().kind === "stopped") {
          const reason = this.process.getProcessState();
          if (reason.kind === "stopped" && reason.reason === "portUnavailable") {
            continue;
          }
        }
      }
    }
    this.state = ManagedRuntimeState.stopped("startFailed");
    throw lastError ?? new Error("Failed to start runtime");
  }

  async stop(mode: RuntimeStopMode = "graceful", signal?: AbortSignal): Promise<void> {
    try {
      await this.process.stop(mode, signal);
      this.state = ManagedRuntimeState.stopped("requested");
    } catch (error) {
      if (isAbortError(error)) {
        throw error;
      }
    }
  }

  getProcessState(): ManagedRuntimeStateType {
    return this.state;
  }

  getInstalledVersion(): Promise<string | null> {
    return this.locator.getInstalledVersion();
  }

  getDiagnostics(): readonly string[] {
    return this.diagnostics.snapshot();
  }

  /** Test hook: simulate unexpected process exit. */
  notifyProcessExit(reason: RuntimeStopReason): void {
    this.process.forceStopped(reason);
    this.state = ManagedRuntimeState.stopped(reason);
  }

  getLastConnection(): RuntimeConnection | null {
    return this.lastConnection;
  }

  markRunning(version: string): void {
    this.process.markRunning(version);
    this.state = ManagedRuntimeState.running(version);
  }
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw new DOMException("The operation was aborted", "AbortError");
  }
}
