import type { ChildProcess } from "node:child_process";
import { spawn } from "node:child_process";

import {
  ManagedRuntimeState,
  type ManagedRuntimeState as ManagedRuntimeStateType,
  type RuntimeStopReason,
} from "../../../domain/entities/RuntimeStatus";
import { RuntimeStartFailedError } from "../../../domain/errors";
import type { DiagnosticBuffer } from "./DiagnosticBuffer";
import { maskArgvForDiagnostics } from "./DiagnosticBuffer";
import { generateSessionToken } from "./sessionToken";

export type RuntimeExitHandler = (reason: RuntimeStopReason) => void;

export type RuntimeProcessStartInput = {
  readonly binaryPath: string;
  readonly host: string;
  readonly port: number;
  readonly dataDir: string;
  readonly sessionToken: string;
  readonly signal?: AbortSignal | undefined;
};

export type RuntimeProcessDeps = {
  readonly spawnProcess?: typeof spawn;
  readonly diagnostics: DiagnosticBuffer;
  readonly onExit?: RuntimeExitHandler;
};

export class RuntimeProcess {
  private child: ChildProcess | null = null;
  private state: ManagedRuntimeStateType = ManagedRuntimeState.stopped("requested");
  private lastSessionToken: string | null = null;
  private readonly spawnProcess: typeof spawn;

  constructor(private readonly deps: RuntimeProcessDeps) {
    this.spawnProcess = deps.spawnProcess ?? spawn;
  }

  getProcessState(): ManagedRuntimeStateType {
    return this.state;
  }

  getLastSessionToken(): string | null {
    return this.lastSessionToken;
  }

  isRunning(): boolean {
    return this.child !== null && this.child.exitCode === null && !this.child.killed;
  }

  async start(
    input: RuntimeProcessStartInput,
  ): Promise<{ readonly port: number; readonly sessionToken: string }> {
    throwIfAborted(input.signal);
    if (this.isRunning()) {
      throw new RuntimeStartFailedError("Runtime process is already running");
    }

    const sessionToken = input.sessionToken || generateSessionToken();
    await this.spawnOnce({
      ...input,
      sessionToken,
    });
    this.lastSessionToken = sessionToken;
    this.state = ManagedRuntimeState.starting();
    return { port: input.port, sessionToken };
  }

  markRunning(version: string): void {
    this.state = ManagedRuntimeState.running(version);
  }

  async stop(mode: "graceful" | "force", signal?: AbortSignal): Promise<void> {
    throwIfAborted(signal);
    const child = this.child;
    if (!child || child.exitCode !== null) {
      this.child = null;
      this.state = ManagedRuntimeState.stopped("requested");
      return;
    }

    await new Promise<void>((resolve) => {
      const onClose = () => {
        resolve();
      };
      child.once("close", onClose);
      if (mode === "force") {
        child.kill("SIGKILL");
      } else if (process.platform === "win32") {
        child.kill();
      } else {
        child.kill("SIGTERM");
      }
    });

    this.child = null;
    this.state = ManagedRuntimeState.stopped("requested");
  }

  forceStopped(reason: RuntimeStopReason): void {
    this.child = null;
    this.state = ManagedRuntimeState.stopped(reason);
  }

  private async spawnOnce(input: RuntimeProcessStartInput): Promise<void> {
    const argv = [
      input.binaryPath,
      "serve",
      "--host",
      input.host,
      "--port",
      String(input.port),
      "--data-dir",
      input.dataDir,
      "--session-token",
      input.sessionToken,
    ];
    this.deps.diagnostics.append("stdout", `[spawn] ${maskArgvForDiagnostics(argv)}`);

    const child = this.spawnProcess(input.binaryPath, argv.slice(1), {
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    });
    this.child = child;

    child.stdout?.on("data", (chunk: Buffer | string) => {
      this.deps.diagnostics.append("stdout", String(chunk));
    });
    child.stderr?.on("data", (chunk: Buffer | string) => {
      this.deps.diagnostics.append("stderr", String(chunk));
    });

    child.on("exit", (code, exitSignal) => {
      if (this.child !== child) {
        return;
      }
      this.child = null;
      const reason: RuntimeStopReason =
        code === 2
          ? "portUnavailable"
          : exitSignal !== null || (code !== null && code !== 0)
            ? "crashed"
            : "requested";
      this.state = ManagedRuntimeState.stopped(reason);
      this.deps.onExit?.(reason);
    });

    child.on("error", () => {
      if (this.child !== child) {
        return;
      }
      this.child = null;
      this.state = ManagedRuntimeState.stopped("startFailed");
      this.deps.onExit?.("startFailed");
    });

    await waitForSpawn(child, 250);
  }
}

function waitForSpawn(child: ChildProcess, delayMs: number): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      cleanup();
      if (child.exitCode !== null) {
        reject(new RuntimeStartFailedError("Runtime process exited during startup"));
        return;
      }
      resolve();
    }, delayMs);
    const onExit = () => {
      cleanup();
      reject(new RuntimeStartFailedError("Runtime process exited during startup"));
    };
    const onError = (error: Error) => {
      cleanup();
      reject(error);
    };
    const cleanup = () => {
      clearTimeout(timer);
      child.off("exit", onExit);
      child.off("error", onError);
    };
    child.once("exit", onExit);
    child.once("error", onError);
  });
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw new DOMException("The operation was aborted", "AbortError");
  }
}
