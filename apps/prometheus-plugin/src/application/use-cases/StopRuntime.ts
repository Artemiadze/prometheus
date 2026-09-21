import {
  ManagedRuntimeState,
  type ManagedRuntimeState as ManagedRuntimeStateType,
} from "../../domain/entities/RuntimeStatus";
import type { Clock } from "../ports/Clock";
import type { RuntimeGateway } from "../ports/RuntimeGateway";
import type { RuntimeSessionRegistry } from "../services/RuntimeSessionRegistry";

export type StopRuntimeResult = {
  readonly runtime: ManagedRuntimeStateType;
  readonly stopped: boolean;
};

export type StopRuntimeOptions = {
  readonly gracefulTimeoutMs?: number;
};

export class StopRuntime {
  constructor(
    private readonly runtime: RuntimeGateway,
    private readonly sessions: RuntimeSessionRegistry,
    private readonly clock: Clock,
  ) {}

  async execute(
    signal?: AbortSignal,
    options: StopRuntimeOptions = {},
  ): Promise<StopRuntimeResult> {
    const session = this.sessions.get();
    if (!session || session.ownership !== "owned") {
      return {
        runtime: this.runtime.getProcessState(),
        stopped: false,
      };
    }

    const timeoutMs = options.gracefulTimeoutMs ?? 100;
    try {
      await Promise.race([
        this.runtime.stop("graceful", signal),
        this.clock.sleep(timeoutMs, signal).then(() => {
          throw new Error("graceful-stop-timeout");
        }),
      ]);
    } catch (error) {
      if (signal?.aborted) {
        throw error;
      }
      await this.runtime.stop("force", signal);
    }

    this.sessions.clear();
    return {
      runtime: ManagedRuntimeState.stopped(),
      stopped: true,
    };
  }
}
