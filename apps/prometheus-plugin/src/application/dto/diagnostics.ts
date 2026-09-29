import type { RecentLogEvent } from "../ports/Logger";

export type DiagnosticsOsInfo = {
  readonly platform: string;
  readonly arch: string;
  readonly release: string;
};

export type DiagnosticsPorts = {
  readonly runtime: number | null;
  readonly ollamaAddress: string;
};

export type DiagnosticsComponents = {
  readonly runtimeKind: string;
  readonly runtimeStopReason: string | null;
  readonly ollamaKind: string;
  readonly selectedModel: string | null;
  readonly modelInstalled: boolean | null;
  readonly indexKind: string;
  readonly documentCount: number | null;
  readonly chunkCount: number | null;
};

export type DiagnosticsSnapshot = {
  readonly pluginVersion: string;
  readonly runtimeVersion: string | null;
  readonly os: DiagnosticsOsInfo;
  readonly ports: DiagnosticsPorts;
  readonly components: DiagnosticsComponents;
  readonly settingsSummary: {
    readonly runtimeMode: string;
    readonly networkAccess: string;
    readonly llmModel: string;
    readonly verboseLogging: boolean;
  };
  readonly processOutput: readonly string[];
  readonly recentEvents: readonly RecentLogEvent[];
  readonly collectedAt: Date;
};
