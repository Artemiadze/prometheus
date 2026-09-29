import { TFolder, type App, type Plugin } from "obsidian";

import { SettingsTab } from "../adapters/inbound/obsidian/SettingsTab";
import { SettingsController } from "../adapters/inbound/obsidian/settings/SettingsController";
import type { StatusStore } from "../adapters/inbound/obsidian/status/StatusStore";
import { RUNTIME_RELEASE_VERSION } from "../adapters/outbound/runtime/runtimeRelease";
import type { Notifier } from "../application/ports/Notifier";
import type { RagGateway } from "../application/ports/RagGateway";
import type { RuntimeGateway } from "../application/ports/RuntimeGateway";
import type { SettingsRepository } from "../application/ports/SettingsRepository";
import { ApplyIgnoredFolderChange } from "../application/services/ApplyIgnoredFolderChange";
import type { DocumentSyncState } from "../application/services/DocumentSyncState";
import { InstallRuntime } from "../application/use-cases/InstallRuntime";
import { SelectLlmModel } from "../application/use-cases/SelectLlmModel";
import type { StartRuntime } from "../application/use-cases/StartRuntime";
import type { StopRuntime } from "../application/use-cases/StopRuntime";
import type { WiredAutoIndexing } from "./wireAutoIndexing";
import type { WiredIndexing } from "./wireIndexing";

export type WireSettingsTabDeps = {
  readonly app: App;
  readonly plugin: Plugin;
  readonly settings: SettingsRepository;
  readonly notifier: Notifier;
  readonly runtimeGateway: RuntimeGateway;
  readonly rag: RagGateway;
  readonly startRuntime: StartRuntime;
  readonly stopRuntime: StopRuntime;
  readonly statusStore: StatusStore;
  readonly indexing: WiredIndexing;
  readonly autoIndexing: WiredAutoIndexing;
  readonly syncState: DocumentSyncState;
  readonly setVerboseLogging?: (enabled: boolean) => void;
  readonly openDiagnostics?: () => void;
  readonly onActivated?: () => void;
};

export type WiredSettingsTab = {
  readonly controller: SettingsController;
  readonly tab: SettingsTab;
  readonly dispose: () => void;
};

export function wireSettingsTab(deps: WireSettingsTabDeps): WiredSettingsTab {
  const installRuntime = new InstallRuntime(deps.runtimeGateway, deps.settings);
  const selectLlmModel = new SelectLlmModel(deps.rag, deps.settings);
  const applyIgnoredFolderChange = new ApplyIgnoredFolderChange(
    deps.rag,
    deps.settings,
    deps.syncState,
    deps.notifier,
  );

  const controller = new SettingsController({
    settings: deps.settings,
    notifier: deps.notifier,
    runtimeGateway: deps.runtimeGateway,
    installRuntime,
    startRuntime: deps.startRuntime,
    stopRuntime: deps.stopRuntime,
    selectLlmModel,
    applyIgnoredFolderChange,
    startReindex: deps.indexing.startReindex,
    statusStore: deps.statusStore,
    autoIndexing: deps.autoIndexing,
    folderExists: (path) => {
      const abstract = deps.app.vault.getAbstractFileByPath(path);
      return abstract instanceof TFolder;
    },
    bundledReleaseVersion: RUNTIME_RELEASE_VERSION,
    ...(deps.setVerboseLogging ? { setVerboseLogging: deps.setVerboseLogging } : {}),
    ...(deps.openDiagnostics ? { openDiagnostics: deps.openDiagnostics } : {}),
    ...(deps.onActivated ? { onActivated: deps.onActivated } : {}),
  });

  const tab = new SettingsTab(deps.app, deps.plugin, controller);

  return {
    controller,
    tab,
    dispose: () => {
      controller.dispose();
    },
  };
}
