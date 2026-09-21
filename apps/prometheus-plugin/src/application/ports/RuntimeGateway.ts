import type { ManagedRuntimeState } from "../../domain/entities/RuntimeStatus";

export type DownloadProgress = {
  readonly percent: number;
};

export type ProgressCallback = (progress: DownloadProgress) => void;

export type RuntimeLocateResult = {
  readonly kind: "managed" | "custom" | "missing";
  readonly version: string | null;
};

export type RuntimeConnection = {
  readonly baseUrl: string;
  readonly sessionToken: string;
};

export type RuntimeStopMode = "graceful" | "force";

/**
 * Outbound port for managed/custom sidecar lifecycle.
 * Does not expose ChildProcess or filesystem APIs.
 */
export interface RuntimeGateway {
  locate(): Promise<RuntimeLocateResult>;
  download(onProgress: ProgressCallback, signal?: AbortSignal): Promise<void>;
  verify(signal?: AbortSignal): Promise<void>;
  start(signal?: AbortSignal): Promise<RuntimeConnection>;
  stop(mode?: RuntimeStopMode, signal?: AbortSignal): Promise<void>;
  getProcessState(): ManagedRuntimeState;
  getInstalledVersion(): Promise<string | null>;
}
