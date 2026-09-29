import type { DiagnosticsSnapshot } from "../dto/diagnostics";
import type { SystemStatus } from "../dto/system";
import type { RecentEventsReader } from "../ports/Logger";
import type { RuntimeGateway } from "../ports/RuntimeGateway";
import type { SettingsRepository } from "../ports/SettingsRepository";
import type { RuntimeSessionRegistry } from "../services/RuntimeSessionRegistry";

export type EnvironmentInfo = {
  readonly pluginVersion: string;
  readonly platform: string;
  readonly arch: string;
  readonly release: string;
};

export type CollectDiagnosticsDeps = {
  readonly runtimeGateway: RuntimeGateway;
  readonly sessions: RuntimeSessionRegistry;
  readonly settings: SettingsRepository;
  readonly recentEvents: RecentEventsReader;
  readonly getStatus: () => SystemStatus | null;
  readonly environment: EnvironmentInfo;
};

/**
 * Assembles a privacy-safe diagnostics snapshot (PLG-75).
 * Never reads session tokens into the snapshot — only the runtime port from baseUrl.
 */
export class CollectDiagnostics {
  constructor(private readonly deps: CollectDiagnosticsDeps) {}

  async execute(): Promise<DiagnosticsSnapshot> {
    const settings = await this.deps.settings.get();
    const status = this.deps.getStatus();
    const processState = this.deps.runtimeGateway.getProcessState();
    const runtimeVersion =
      processState.kind === "running"
        ? processState.version
        : processState.kind === "incompatible"
          ? processState.installedVersion
          : await this.deps.runtimeGateway.getInstalledVersion();

    const session = this.deps.sessions.get();
    const runtimePort = session ? extractPort(session.connection.baseUrl) : null;

    const runtime = status?.runtime.runtime ?? processState;
    const ollama = status?.runtime.ollama;
    const selectedModel = status?.runtime.selectedModel ?? null;
    const index = status?.index;

    return {
      pluginVersion: this.deps.environment.pluginVersion,
      runtimeVersion,
      os: {
        platform: this.deps.environment.platform,
        arch: this.deps.environment.arch,
        release: this.deps.environment.release,
      },
      ports: {
        runtime: runtimePort,
        ollamaAddress: settings.ollamaAddress,
      },
      components: {
        runtimeKind: runtime.kind,
        runtimeStopReason: runtime.kind === "stopped" ? runtime.reason : null,
        ollamaKind: ollama?.kind ?? "unknown",
        selectedModel: selectedModel?.name ?? (settings.llmModel || null),
        modelInstalled: selectedModel ? selectedModel.installed : null,
        indexKind: index?.kind ?? "unknown",
        documentCount: index?.kind === "ready" ? index.documentCount : null,
        chunkCount: index?.kind === "ready" ? index.chunkCount : null,
      },
      settingsSummary: {
        runtimeMode: settings.runtimeMode,
        networkAccess: settings.networkAccess,
        llmModel: settings.llmModel,
        verboseLogging: settings.verboseLogging,
      },
      processOutput: this.deps.runtimeGateway.getDiagnostics(),
      recentEvents: this.deps.recentEvents.snapshot(),
      collectedAt: new Date(),
    };
  }
}

function extractPort(baseUrl: string): number | null {
  try {
    const url = new URL(baseUrl);
    if (url.port) {
      return Number(url.port);
    }
    if (url.protocol === "https:") {
      return 443;
    }
    if (url.protocol === "http:") {
      return 80;
    }
    return null;
  } catch {
    return null;
  }
}
