import {
  ManagedRuntimeState,
  type ManagedRuntimeState as ManagedRuntimeStateType,
} from "../../domain/entities/RuntimeStatus";
import {
  isAbortError,
  NetworkAccessDisabledError,
  RuntimeChecksumMismatchError,
} from "../../domain/errors";
import type { ProgressCallback, RuntimeGateway } from "../ports/RuntimeGateway";
import type { SettingsRepository } from "../ports/SettingsRepository";

export type InstallRuntimeProgressCallback = (state: ManagedRuntimeStateType) => void;

export class InstallRuntime {
  constructor(
    private readonly runtime: RuntimeGateway,
    private readonly settings: SettingsRepository,
  ) {}

  async execute(
    onState?: InstallRuntimeProgressCallback,
    signal?: AbortSignal,
  ): Promise<ManagedRuntimeStateType> {
    const settings = await this.settings.get();
    const located = await this.runtime.locate();

    try {
      if (located.kind === "missing") {
        if (settings.networkAccess === "disabled") {
          throw new NetworkAccessDisabledError();
        }
        const progress: ProgressCallback = (download) => {
          onState?.(ManagedRuntimeState.downloading(download.percent));
        };
        await this.runtime.download(progress, signal);
      }

      onState?.(ManagedRuntimeState.verifying());
      await this.runtime.verify(signal);
      return ManagedRuntimeState.verifying();
    } catch (error) {
      if (isAbortError(error)) {
        throw error;
      }
      if (
        error instanceof RuntimeChecksumMismatchError ||
        error instanceof NetworkAccessDisabledError
      ) {
        throw error;
      }
      throw error;
    }
  }
}
