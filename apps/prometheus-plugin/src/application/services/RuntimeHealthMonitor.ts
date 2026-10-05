import {
  ManagedRuntimeState,
  type ManagedRuntimeState as ManagedRuntimeStateType,
} from "../../domain/entities/RuntimeStatus";
import { isAbortError, RuntimeVersionIncompatibleError } from "../../domain/errors";
import type { Clock } from "../ports/Clock";
import type { RagGateway } from "../ports/RagGateway";
import type { RuntimeSessionRegistry } from "./RuntimeSessionRegistry";

export type RuntimeHealthMonitorOptions = {
  readonly intervalMs?: number;
  readonly errorBackoffFactor?: number;
  readonly maxIntervalMs?: number;
  /** Failures required before declaring the runtime unavailable / requesting restart. */
  readonly failureThreshold?: number;
  /** Ignore unavailable restarts until the session has been up at least this long. */
  readonly startupGraceMs?: number;
};

export type RuntimeHealthMonitorCallbacks = {
  readonly onStateChange?: (state: ManagedRuntimeStateType) => void;
  readonly onUnavailable?: () => void;
};

/**
 * Periodic health checks while a runtime session exists. Idle interval keeps load low.
 *
 * Transient failures (cold start, brief loopback blips) must not SIGKILL a live
 * sidecar via supervisor restart — require consecutive failures after a grace period.
 */
export class RuntimeHealthMonitor {
  private readonly intervalMs: number;
  private readonly errorBackoffFactor: number;
  private readonly maxIntervalMs: number;
  private readonly failureThreshold: number;
  private readonly startupGraceMs: number;
  private loopPromise: Promise<void> | null = null;
  private consecutiveFailures = 0;
  private sessionSeenAtMs: number | null = null;

  constructor(
    private readonly rag: RagGateway,
    private readonly sessions: RuntimeSessionRegistry,
    private readonly clock: Clock,
    options: RuntimeHealthMonitorOptions = {},
  ) {
    this.intervalMs = options.intervalMs ?? 30_000;
    this.errorBackoffFactor = options.errorBackoffFactor ?? 1.5;
    this.maxIntervalMs = options.maxIntervalMs ?? 120_000;
    this.failureThreshold = options.failureThreshold ?? 3;
    this.startupGraceMs = options.startupGraceMs ?? 60_000;
  }

  start(callbacks: RuntimeHealthMonitorCallbacks, signal?: AbortSignal): void {
    if (this.loopPromise) {
      return;
    }
    this.loopPromise = this.runLoop(callbacks, signal).finally(() => {
      this.loopPromise = null;
    });
  }

  async stop(): Promise<void> {
    if (!this.loopPromise) {
      return;
    }
    await this.loopPromise.catch((error: unknown) => {
      if (!isAbortError(error)) {
        throw error;
      }
    });
  }

  private async runLoop(
    callbacks: RuntimeHealthMonitorCallbacks,
    signal?: AbortSignal,
  ): Promise<void> {
    let waitMs = this.intervalMs;
    try {
      for (;;) {
        throwIfAborted(signal);
        if (!this.sessions.get()) {
          this.consecutiveFailures = 0;
          this.sessionSeenAtMs = null;
          await this.clock.sleep(this.intervalMs, signal);
          continue;
        }
        if (this.sessionSeenAtMs === null) {
          this.sessionSeenAtMs = this.clock.now().getTime();
        }
        try {
          const health = await this.rag.health(signal);
          this.consecutiveFailures = 0;
          callbacks.onStateChange?.(ManagedRuntimeState.running(health.version));
          waitMs = this.intervalMs;
        } catch (error) {
          if (isAbortError(error)) {
            throw error;
          }
          if (error instanceof RuntimeVersionIncompatibleError) {
            this.consecutiveFailures = 0;
            callbacks.onStateChange?.(
              ManagedRuntimeState.incompatible(error.installedVersion, error.requiredRange),
            );
          } else {
            this.consecutiveFailures += 1;
            const sessionAgeMs = this.clock.now().getTime() - (this.sessionSeenAtMs ?? 0);
            const pastGrace = sessionAgeMs >= this.startupGraceMs;
            const thresholdMet = this.consecutiveFailures >= this.failureThreshold;
            if (thresholdMet && pastGrace) {
              callbacks.onUnavailable?.();
              callbacks.onStateChange?.(ManagedRuntimeState.stopped("crashed"));
            }
          }
          waitMs = Math.min(this.maxIntervalMs, Math.round(waitMs * this.errorBackoffFactor));
        }
        await this.clock.sleep(waitMs, signal);
      }
    } catch (error) {
      if (!isAbortError(error)) {
        throw error;
      }
    }
  }
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw new DOMException("The operation was aborted", "AbortError");
  }
}
