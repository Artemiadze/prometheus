import { HttpRagGateway, RuntimeHttpClient } from "../adapters/outbound/rag-api";
import { ManagedRuntimeGateway, nodeHttpFetch, type FetchFn } from "../adapters/outbound/runtime";
import { SystemClock } from "../adapters/outbound/system/SystemClock";
import type { ManagedRuntimeState } from "../domain/entities/RuntimeStatus";
import type { RuntimeStopReason } from "../domain/entities/RuntimeStatus";
import { RuntimeHealthMonitor } from "../application/services/RuntimeHealthMonitor";
import { RuntimeSessionRegistry } from "../application/services/RuntimeSessionRegistry";
import { RuntimeSupervisor } from "../application/services/RuntimeSupervisor";
import type { Notifier } from "../application/ports/Notifier";
import type { Logger } from "../application/ports/Logger";
import type { SettingsRepository } from "../application/ports/SettingsRepository";
import { StartRuntime } from "../application/use-cases/StartRuntime";
import { StopRuntime } from "../application/use-cases/StopRuntime";

export type WireRuntimeLifecycleDeps = {
  readonly settings: SettingsRepository;
  readonly notifier: Notifier;
  readonly logger?: Logger;
  readonly fetchFn?: FetchFn;
  readonly onRuntimeStateChange?: (state: ManagedRuntimeState) => void;
};

export type WiredRuntimeLifecycle = {
  readonly runtimeGateway: ManagedRuntimeGateway;
  readonly sessions: RuntimeSessionRegistry;
  readonly rag: HttpRagGateway;
  readonly startRuntime: StartRuntime;
  readonly stopRuntime: StopRuntime;
  readonly dispose: () => void;
};

/**
 * Wires runtime adapter, HTTP client, monitor, supervisor, and unload cleanup.
 * Does not auto-start the runtime on plugin load (PLG-78).
 */
export function wireRuntimeLifecycle(deps: WireRuntimeLifecycleDeps): WiredRuntimeLifecycle {
  const clock = new SystemClock();
  const sessions = new RuntimeSessionRegistry();
  const abortController = new AbortController();
  const supervisorHolder: { supervisor: RuntimeSupervisor | null } = { supervisor: null };
  // Prefer Node HTTP: Chromium fetch can fail on loopback (CORS / private-network).
  const fetchFn = deps.fetchFn ?? nodeHttpFetch;

  const runtimeGateway = new ManagedRuntimeGateway({
    settings: deps.settings,
    fetchFn,
    onProcessExit: (reason: RuntimeStopReason) => {
      supervisorHolder.supervisor?.handleProcessExit(reason, abortController.signal);
    },
  });

  const httpClient = new RuntimeHttpClient({
    sessions,
    getHealthBaseUrl: () => sessions.get()?.connection.baseUrl ?? "http://127.0.0.1:8765",
    fetchFn,
    onUnauthorized: () => {
      sessions.clear();
    },
  });
  const rag = new HttpRagGateway(httpClient);

  const startRuntime = new StartRuntime(runtimeGateway, rag, deps.settings, sessions, clock);
  const stopRuntime = new StopRuntime(runtimeGateway, sessions, clock);
  supervisorHolder.supervisor = new RuntimeSupervisor(
    startRuntime,
    sessions,
    clock,
    deps.notifier,
    {},
    deps.logger,
  );

  const monitor = new RuntimeHealthMonitor(rag, sessions, clock);
  monitor.start(
    {
      onStateChange: (state) => {
        deps.onRuntimeStateChange?.(state);
        if (state.kind === "running") {
          runtimeGateway.markRunning(state.version);
          supervisorHolder.supervisor?.notifyStarted();
          deps.logger?.event("runtime.started", { version: state.version });
        } else if (state.kind === "stopped") {
          deps.logger?.event("runtime.stopped", { reason: state.reason });
        }
      },
      onUnavailable: () => {
        supervisorHolder.supervisor?.handleHealthLost(abortController.signal);
      },
    },
    abortController.signal,
  );

  const dispose = (): void => {
    abortController.abort();
    void stopRuntime.execute(abortController.signal).catch(() => undefined);
    void supervisorHolder.supervisor?.flush().catch(() => undefined);
    void monitor.stop().catch(() => undefined);
  };

  return {
    runtimeGateway,
    sessions,
    rag,
    startRuntime,
    stopRuntime,
    dispose,
  };
}
