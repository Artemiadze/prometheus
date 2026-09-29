import type { App } from "obsidian";
import { arch, platform, release } from "node:os";

import { DiagnosticsModal } from "../adapters/inbound/obsidian/diagnostics/DiagnosticsModal";
import type { StatusStore } from "../adapters/inbound/obsidian/status/StatusStore";
import type { Notifier } from "../application/ports/Notifier";
import type { RecentEventsReader } from "../application/ports/Logger";
import type { RuntimeGateway } from "../application/ports/RuntimeGateway";
import type { SettingsRepository } from "../application/ports/SettingsRepository";
import type { RuntimeSessionRegistry } from "../application/services/RuntimeSessionRegistry";
import { CollectDiagnostics } from "../application/use-cases/CollectDiagnostics";

export type WireDiagnosticsDeps = {
  readonly app: App;
  readonly pluginVersion: string;
  readonly runtimeGateway: RuntimeGateway;
  readonly sessions: RuntimeSessionRegistry;
  readonly settings: SettingsRepository;
  readonly recentEvents: RecentEventsReader;
  readonly statusStore: Pick<StatusStore, "getState">;
  readonly notifier: Notifier;
};

export type WiredDiagnostics = {
  readonly collect: CollectDiagnostics;
  readonly openDiagnostics: (app?: App) => void;
};

export function wireDiagnostics(deps: WireDiagnosticsDeps): WiredDiagnostics {
  const collect = new CollectDiagnostics({
    runtimeGateway: deps.runtimeGateway,
    sessions: deps.sessions,
    settings: deps.settings,
    recentEvents: deps.recentEvents,
    getStatus: () => deps.statusStore.getState().status,
    environment: {
      pluginVersion: deps.pluginVersion,
      platform: platform(),
      arch: arch(),
      release: release(),
    },
  });

  let openModal: DiagnosticsModal | null = null;

  const openDiagnostics = (app: App = deps.app): void => {
    if (openModal) {
      openModal.close();
    }
    openModal = new DiagnosticsModal(app, {
      collect,
      notifier: deps.notifier,
    });
    openModal.open();
  };

  return { collect, openDiagnostics };
}
