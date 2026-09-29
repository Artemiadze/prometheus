import type { RuntimeStopReason } from "../../domain/entities/RuntimeStatus";
import { isAbortError } from "../../domain/errors";
import type { Notifier } from "../ports/Notifier";
import type { Logger } from "../ports/Logger";
import type { Clock } from "../ports/Clock";
import type { RuntimeSessionRegistry } from "./RuntimeSessionRegistry";
import type { StartRuntime } from "../use-cases/StartRuntime";

export type RuntimeSupervisorOptions = {
  readonly maxRestarts?: number;
  readonly restartBackoffMs?: number;
  readonly stableUptimeMs?: number;
};

/**
 * Bounded automatic restart when the owned runtime exits unexpectedly.
 */
export class RuntimeSupervisor {
  private readonly maxRestarts: number;
  private readonly restartBackoffMs: number;
  private readonly stableUptimeMs: number;
  private restartCount = 0;
  private lastStartAt: number | null = null;
  private restartChain: Promise<void> = Promise.resolve();
  private readonly logger: Logger | null;

  constructor(
    private readonly startRuntime: StartRuntime,
    private readonly sessions: RuntimeSessionRegistry,
    private readonly clock: Clock,
    private readonly notifier: Notifier,
    options: RuntimeSupervisorOptions = {},
    logger?: Logger,
  ) {
    this.maxRestarts = options.maxRestarts ?? 2;
    this.restartBackoffMs = options.restartBackoffMs ?? 1_000;
    this.stableUptimeMs = options.stableUptimeMs ?? 60_000;
    this.logger = logger ?? null;
  }

  notifyStarted(): void {
    const now = this.clock.now().getTime();
    if (this.lastStartAt !== null && now - this.lastStartAt >= this.stableUptimeMs) {
      this.restartCount = 0;
    }
    this.lastStartAt = now;
  }

  handleProcessExit(reason: RuntimeStopReason, signal?: AbortSignal): void {
    if (reason === "requested") {
      return;
    }
    if (!this.sessions.isOwned()) {
      return;
    }
    this.restartChain = this.restartChain.then(() => this.tryRestart(reason, signal));
  }

  handleHealthLost(signal?: AbortSignal): void {
    if (!this.sessions.isOwned()) {
      return;
    }
    this.restartChain = this.restartChain.then(() => this.tryRestart("crashed", signal));
  }

  async flush(): Promise<void> {
    await this.restartChain;
  }

  private async tryRestart(reason: RuntimeStopReason, signal?: AbortSignal): Promise<void> {
    if (this.restartCount >= this.maxRestarts) {
      this.logger?.event("runtime.restart_gave_up", { reason });
      this.notifier.warning(
        "Prometheus runtime stopped unexpectedly. Restart it manually from the status panel.",
      );
      return;
    }
    this.restartCount += 1;
    this.logger?.event("runtime.restart_attempt", {
      reason,
      attempt: this.restartCount,
    });
    const backoff = this.restartBackoffMs * this.restartCount;
    try {
      await this.clock.sleep(backoff, signal);
      const result = await this.startRuntime.execute(signal);
      if (result.kind === "ready" && result.ownership === "owned") {
        this.notifyStarted();
        return;
      }
      if (result.kind === "missing") {
        this.notifier.error("Prometheus runtime is not installed.");
        return;
      }
      if (result.kind === "incompatible") {
        this.notifier.error("Prometheus runtime version is incompatible. Update the sidecar.");
        return;
      }
    } catch (error) {
      if (isAbortError(error)) {
        return;
      }
      this.logger?.error("RUNTIME_START_FAILED", { reason });
      this.notifier.error("Prometheus runtime restart failed.");
    }
  }
}
