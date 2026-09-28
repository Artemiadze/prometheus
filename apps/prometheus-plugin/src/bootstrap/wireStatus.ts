import { SystemClock } from "../adapters/outbound/system/SystemClock";
import { StatusStore } from "../adapters/inbound/obsidian/status/StatusStore";
import type { ActiveJobRegistry } from "../application/services/ActiveJobRegistry";
import type { Notifier } from "../application/ports/Notifier";
import type { RagGateway } from "../application/ports/RagGateway";
import type { RuntimeGateway } from "../application/ports/RuntimeGateway";
import type { SettingsRepository } from "../application/ports/SettingsRepository";
import { GetSystemStatus } from "../application/use-cases/GetSystemStatus";
import { InstallRuntime } from "../application/use-cases/InstallRuntime";
import { SelectLlmModel } from "../application/use-cases/SelectLlmModel";
import type { StartRuntime } from "../application/use-cases/StartRuntime";
import type { WiredIndexing } from "./wireIndexing";

export type WireStatusDeps = {
  readonly rag: RagGateway;
  readonly runtimeGateway: RuntimeGateway;
  readonly settings: SettingsRepository;
  readonly startRuntime: StartRuntime;
  readonly jobRegistry: ActiveJobRegistry;
  readonly indexing: WiredIndexing;
  readonly notifier?: Notifier;
};

export type WiredStatus = {
  readonly store: StatusStore;
  readonly getSystemStatus: GetSystemStatus;
  readonly dispose: () => void;
};

export function wireStatus(deps: WireStatusDeps): WiredStatus {
  const clock = new SystemClock();
  const getSystemStatus = new GetSystemStatus(deps.rag, deps.runtimeGateway, deps.settings, clock, {
    minIntervalMs: 1_000,
    getActiveJob: () => deps.jobRegistry.get(),
  });
  const installRuntime = new InstallRuntime(deps.runtimeGateway, deps.settings);
  const selectLlmModel = new SelectLlmModel(deps.rag, deps.settings);

  const store = new StatusStore({
    getSystemStatus,
    installRuntime,
    startRuntime: deps.startRuntime,
    selectLlmModel,
    startInitialSync: deps.indexing.startInitialSync,
    startReindex: deps.indexing.startReindex,
    cancelActive: deps.indexing.cancelActive,
  });

  return {
    store,
    getSystemStatus,
    dispose: () => {
      store.dispose();
    },
  };
}
