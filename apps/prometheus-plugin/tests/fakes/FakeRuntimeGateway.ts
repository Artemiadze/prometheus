import type {
  DownloadProgress,
  ProgressCallback,
  RuntimeConnection,
  RuntimeGateway,
  RuntimeLocateResult,
} from "../../src/application/ports/RuntimeGateway";
import {
  ManagedRuntimeState,
  type ManagedRuntimeState as ManagedRuntimeStateType,
} from "../../src/domain/entities/RuntimeStatus";

export class FakeRuntimeGateway implements RuntimeGateway {
  private state: ManagedRuntimeStateType = ManagedRuntimeState.missing();
  private installedVersion: string | null = null;
  private locateKind: RuntimeLocateResult["kind"] = "missing";
  lastConnection: RuntimeConnection | null = null;
  readonly downloadProgress: DownloadProgress[] = [];

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
  }

  async start(signal?: AbortSignal): Promise<RuntimeConnection> {
    throwIfAborted(signal);
    this.state = ManagedRuntimeState.starting();
    const connection: RuntimeConnection = {
      baseUrl: "http://127.0.0.1:8765",
      sessionToken: "test-session-token",
    };
    this.lastConnection = connection;
    this.state = ManagedRuntimeState.running(this.installedVersion ?? "0.1.0");
    return connection;
  }

  async stop(signal?: AbortSignal): Promise<void> {
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
