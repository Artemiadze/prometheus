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
import {
  isAbortError,
  RuntimeNotInstalledError,
  RuntimeStartFailedError,
} from "../../../domain/errors";
import { DiagnosticBuffer } from "./DiagnosticBuffer";
import { nodeHttpFetch } from "./nodeHttpFetch";
import { killOrphanRuntimeServes } from "./orphanCleanup";
import { allocateLoopbackPort } from "./portAllocator";
import { RuntimeDownloader, type FetchFn } from "./RuntimeDownloader";
import { RuntimeLocator } from "./RuntimeLocator";
import { RuntimeProcess, type RuntimeExitHandler } from "./RuntimeProcess";
import { buildRuntimeSpawnEnv } from "./runtimeSpawnEnv";
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
  private readonly settings: SettingsRepository;
  private readonly locator: RuntimeLocator;
  private readonly downloader: RuntimeDownloader;
  private readonly process: RuntimeProcess;
  private state: ManagedRuntimeStateType = ManagedRuntimeState.missing();
  private lastConnection: RuntimeConnection | null = null;

  constructor(options: ManagedRuntimeGatewayOptions) {
    this.diagnostics = options.diagnostics ?? new DiagnosticBuffer();
    this.settings = options.settings;
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
      // Node HTTP avoids Obsidian Chromium CORS / private-network blocks on loopback mirrors.
      fetchFn: options.fetchFn ?? nodeHttpFetch,
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
    void this.refreshInstalledState();
  }

  locate(): Promise<RuntimeLocateResult> {
    return this.locator.locate();
  }

  /** Align in-memory state with an already-installed managed/custom binary. */
  async refreshInstalledState(): Promise<void> {
    if (
      this.state.kind === "running" ||
      this.state.kind === "starting" ||
      this.state.kind === "downloading" ||
      this.state.kind === "verifying"
    ) {
      return;
    }
    const located = await this.locator.locate();
    this.state =
      located.kind === "missing"
        ? ManagedRuntimeState.missing()
        : ManagedRuntimeState.stopped("requested");
  }

  async download(onProgress: ProgressCallback, signal?: AbortSignal): Promise<void> {
    this.state = ManagedRuntimeState.downloading(0);
    const progress: ProgressCallback = (value) => {
      this.state = ManagedRuntimeState.downloading(value.percent);
      onProgress(value);
    };
    try {
      await this.downloader.download(progress, signal);
      this.state = ManagedRuntimeState.verifying();
    } catch (error) {
      await this.refreshInstalledState();
      this.diagnostics.append(
        "stderr",
        `[download] ${error instanceof Error ? error.message : String(error)}`,
      );
      throw error;
    }
  }

  async verify(signal?: AbortSignal): Promise<void> {
    this.state = ManagedRuntimeState.verifying();
    try {
      await this.downloader.verifyInstalledBinary(signal);
      this.state = ManagedRuntimeState.stopped("requested");
    } catch (error) {
      await this.refreshInstalledState();
      this.diagnostics.append(
        "stderr",
        `[verify] ${error instanceof Error ? error.message : String(error)}`,
      );
      throw error;
    }
  }

  async start(signal?: AbortSignal): Promise<RuntimeConnection> {
    const binary = await this.locator.resolveBinaryPath();
    if (!binary) {
      this.state = ManagedRuntimeState.missing();
      throw new RuntimeNotInstalledError();
    }

    const dataDir = this.locator.dataRootPath();
    this.diagnostics.append("stdout", `[start] binary=${binary} dataDir=${dataDir}`);

    // Only force-stop a live tracked child (avoids no-op noise; restart path still clears it).
    if (this.process.isRunning()) {
      await this.process.stop("force", signal).catch(() => undefined);
    }
    const orphans = await killOrphanRuntimeServes(binary, dataDir, (stream, chunk) => {
      this.diagnostics.append(stream, chunk);
    });
    if (orphans > 0) {
      this.diagnostics.append("stdout", `[cleanup] cleared ${orphans} orphan runtime process(es)`);
    }

    const pluginSettings = await this.settings.get();
    const spawnEnv = await buildRuntimeSpawnEnv(dataDir, process.env, {
      llmContextSize: pluginSettings.llmContextSize,
    });
    if (spawnEnv.PROMETHEUS_EMBEDDING_ALLOW_DOWNLOAD === "true") {
      this.diagnostics.append(
        "stdout",
        "[start] embedding cache incomplete — enabling PROMETHEUS_EMBEDDING_ALLOW_DOWNLOAD",
      );
    }

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
          env: spawnEnv,
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
        this.diagnostics.append("stderr", `[start] attempt ${attempt + 1}: ${lastError.message}`);
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
    throw new RuntimeStartFailedError(
      lastError?.message ? `Prometheus runtime failed to start: ${lastError.message}` : undefined,
    );
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

  getDataRootPath(): string {
    return this.locator.dataRootPath();
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
