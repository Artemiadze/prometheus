import type {
  DownloadProgress,
  ProgressCallback,
  RuntimeConnection,
  RuntimeGateway,
  RuntimeLocateResult,
  RuntimeStopMode,
} from "../../src/application/ports/RuntimeGateway";
import {
  ManagedRuntimeState,
  type ManagedRuntimeState as ManagedRuntimeStateType,
} from "../../src/domain/entities/RuntimeStatus";
import { RuntimeChecksumMismatchError } from "../../src/domain/errors";

export class FakeRuntimeGateway implements RuntimeGateway {
  private state: ManagedRuntimeStateType = ManagedRuntimeState.missing();
  private installedVersion: string | null = null;
  private locateKind: RuntimeLocateResult["kind"] = "missing";
  lastConnection: RuntimeConnection | null = null;
  readonly downloadProgress: DownloadProgress[] = [];
  readonly stopCalls: RuntimeStopMode[] = [];
  startCalls = 0;
  verifyShouldFail = false;
  hangGracefulStop = false;

  setLocateResult(kind: RuntimeLocateResult["kind"], version: string | null = null): void {
    this.locateKind = kind;
    this.installedVersion = version;
    if (kind === "missing") {
      this.state = ManagedRuntimeState.missing();
    } else if (version) {
      this.state = ManagedRuntimeState.stopped();
    }
  }

  async locate(): Promise<RuntimeLocateResult> {
    return { kind: this.locateKind, version: this.installedVersion };
  }

  async download(onProgress: ProgressCallback, signal?: AbortSignal): Promise<void> {
    throwIfAborted(signal);
    this.state = ManagedRuntimeState.downloading(0);
    for (const percent of [25, 50, 75, 100]) {
      throwIfAborted(signal);
      const progress = { percent };
      this.downloadProgress.push(progress);
      onProgress(progress);
      this.state = ManagedRuntimeState.downloading(percent);
    }
    this.installedVersion = this.installedVersion ?? "0.1.0";
    this.locateKind = "managed";
    this.state = ManagedRuntimeState.verifying();
  }

  async verify(signal?: AbortSignal): Promise<void> {
    throwIfAborted(signal);
    this.state = ManagedRuntimeState.verifying();
    if (this.verifyShouldFail) {
      throw new RuntimeChecksumMismatchError();
    }
  }

  async start(signal?: AbortSignal): Promise<RuntimeConnection> {
    throwIfAborted(signal);
    this.startCalls += 1;
    this.state = ManagedRuntimeState.starting();
    const connection: RuntimeConnection = {
      baseUrl: "http://127.0.0.1:8765",
      sessionToken: "test-session-token",
    };
    this.lastConnection = connection;
    this.state = ManagedRuntimeState.running(this.installedVersion ?? "0.1.0");
    return connection;
  }

  async stop(mode: RuntimeStopMode = "graceful", signal?: AbortSignal): Promise<void> {
    throwIfAborted(signal);
    this.stopCalls.push(mode);
    if (mode === "graceful" && this.hangGracefulStop) {
      await new Promise<void>(() => {
        /* never resolves — StopRuntime races FakeClock timeout */
      });
    }
    throwIfAborted(signal);
    this.state = ManagedRuntimeState.stopped();
  }

  getProcessState(): ManagedRuntimeStateType {
    return this.state;
  }

  async getInstalledVersion(): Promise<string | null> {
    return this.installedVersion;
  }
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw new DOMException("The operation was aborted", "AbortError");
  }
}
