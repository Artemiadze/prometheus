import type { App } from "obsidian";

import { OnboardingController } from "../adapters/inbound/obsidian/onboarding/OnboardingController";
import { OnboardingModal } from "../adapters/inbound/obsidian/onboarding/OnboardingModal";
import type { SettingsRepository } from "../application/ports/SettingsRepository";
import { InstallRuntime } from "../application/use-cases/InstallRuntime";
import { SelectLlmModel } from "../application/use-cases/SelectLlmModel";
import type { StartRuntime } from "../application/use-cases/StartRuntime";
import type { RuntimeGateway } from "../application/ports/RuntimeGateway";
import type { RagGateway } from "../application/ports/RagGateway";
import type { GetSystemStatus } from "../application/use-cases/GetSystemStatus";
import type { WiredIndexing } from "./wireIndexing";

export type WireOnboardingDeps = {
  readonly settings: SettingsRepository;
  readonly runtimeGateway: RuntimeGateway;
  readonly rag: RagGateway;
  readonly startRuntime: StartRuntime;
  readonly getSystemStatus: GetSystemStatus;
  readonly indexing: WiredIndexing;
  readonly onActivated?: () => void;
};

export type WiredOnboarding = {
  readonly openOnboarding: (app: App) => void;
  readonly openOnboardingIfNeeded: (app: App) => Promise<void>;
};

export function wireOnboarding(deps: WireOnboardingDeps): WiredOnboarding {
  const installRuntime = new InstallRuntime(deps.runtimeGateway, deps.settings);
  const selectLlmModel = new SelectLlmModel(deps.rag, deps.settings);

  const createController = (): OnboardingController =>
    new OnboardingController({
      installRuntime: (onState, signal) =>
        installRuntime.execute(onState, signal).then(() => undefined),
      startRuntime: async (signal) => {
        const result = await deps.startRuntime.execute(signal);
        if (result.kind !== "ready") {
          throw new Error(
            result.kind === "missing"
              ? "Prometheus runtime is not installed"
              : "Prometheus runtime version is incompatible",
          );
        }
        deps.onActivated?.();
      },
      getStatus: (signal) => deps.getSystemStatus.execute({ pollAllowed: true, signal }),
      listModels: (signal) => selectLlmModel.list(signal),
      selectModel: async (name, signal) => {
        await selectLlmModel.select(name, signal);
      },
      startInitialSync: (signal, onProgress) => deps.indexing.startInitialSync(signal, onProgress),
      cancelActive: (signal) => deps.indexing.cancelActive(signal),
      markCompleted: async () => {
        const settings = await deps.settings.get();
        if (!settings.hasCompletedOnboarding) {
          await deps.settings.save({ ...settings, hasCompletedOnboarding: true });
        }
      },
    });

  const openOnboarding = (app: App): void => {
    const controller = createController();
    new OnboardingModal(app, { controller }).open();
  };

  const openOnboardingIfNeeded = async (app: App): Promise<void> => {
    const settings = await deps.settings.get();
    if (!settings.hasCompletedOnboarding) {
      openOnboarding(app);
    }
  };

  return { openOnboarding, openOnboardingIfNeeded };
}
