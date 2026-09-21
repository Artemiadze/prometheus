import {
  ManagedRuntimeState,
  type ManagedRuntimeState as ManagedRuntimeStateType,
} from "../../domain/entities/RuntimeStatus";
import { isAbortError, RuntimeChecksumMismatchError } from "../../domain/errors";
import type { ProgressCallback, RuntimeGateway } from "../ports/RuntimeGateway";

export type InstallRuntimeProgressCallback = (state: ManagedRuntimeStateType) => void;

export class InstallRuntime {
  constructor(private readonly runtime: RuntimeGateway) {}

  async execute(
    onState?: InstallRuntimeProgressCallback,
    signal?: AbortSignal,
  ): Promise<ManagedRuntimeStateType> {
    const progress: ProgressCallback = (download) => {
      onState?.(ManagedRuntimeState.downloading(download.percent));
    };

    try {
      await this.runtime.download(progress, signal);
      onState?.(ManagedRuntimeState.verifying());
      await this.runtime.verify(signal);
      return ManagedRuntimeState.verifying();
    } catch (error) {
      if (isAbortError(error)) {
        throw error;
      }
      if (error instanceof RuntimeChecksumMismatchError) {
        throw error;
      }
      throw error;
    }
  }
}
