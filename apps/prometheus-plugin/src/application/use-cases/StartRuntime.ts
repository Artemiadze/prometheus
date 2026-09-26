import {
  ManagedRuntimeState,
  type ManagedRuntimeState as ManagedRuntimeStateType,
} from "../../domain/entities/RuntimeStatus";
import type { Clock } from "../ports/Clock";
import type { RagGateway } from "../ports/RagGateway";
import type { RuntimeConnection, RuntimeGateway } from "../ports/RuntimeGateway";
import type { SettingsRepository } from "../ports/SettingsRepository";
import type { RuntimeSessionRegistry } from "../services/RuntimeSessionRegistry";
import { isAbortError, RuntimeVersionIncompatibleError } from "../../domain/errors";
import type { HealthInfo } from "../dto/rag";

export type StartRuntimeResult =
  | {
      readonly kind: "missing";
      readonly runtime: ManagedRuntimeStateType;
      readonly spawned: false;
    }
  | {
      readonly kind: "ready";
      readonly runtime: ManagedRuntimeStateType;
      readonly connection: RuntimeConnection;
      readonly ownership: "owned" | "external";
      readonly spawned: boolean;
    }
  | {
      readonly kind: "incompatible";
      readonly runtime: ManagedRuntimeStateType;
      readonly spawned: boolean;
    };

export type StartRuntimeOptions = {
  readonly healthPollIntervalMs?: number;
  readonly healthTimeoutMs?: number;
};

const EXTERNAL_CONNECTION: RuntimeConnection = {
  baseUrl: "http://127.0.0.1:0",
  sessionToken: "external-session",
};

export class StartRuntime {
  constructor(
    private readonly runtime: RuntimeGateway,
    private readonly rag: RagGateway,
    private readonly settings: SettingsRepository,
    private readonly sessions: RuntimeSessionRegistry,
    private readonly clock: Clock,
  ) {}

  async execute(
    signal?: AbortSignal,
    options: StartRuntimeOptions = {},
  ): Promise<StartRuntimeResult> {
    await this.settings.get();

    const probe = await this.probeHealth(signal);
    if (probe.kind === "incompatible") {
      return {
        kind: "incompatible",
        runtime: ManagedRuntimeState.incompatible(
          probe.error.installedVersion,
          probe.error.requiredRange,
        ),
        spawned: false,
      };
    }
    if (probe.kind === "ready") {
      const existing = this.sessions.get()?.connection ?? EXTERNAL_CONNECTION;
      this.sessions.set({ connection: existing, ownership: "external" });
      return {
        kind: "ready",
        runtime: ManagedRuntimeState.running(probe.health.version),
        connection: existing,
        ownership: "external",
        spawned: false,
      };
    }

    const located = await this.runtime.locate();
    if (located.kind === "missing") {
      return {
        kind: "missing",
        runtime: ManagedRuntimeState.missing(),
        spawned: false,
      };
    }

    await this.runtime.verify(signal);

    const connection = await this.runtime.start(signal);
    this.sessions.set({ connection, ownership: "owned" });

    let health: HealthInfo;
    try {
      health = await this.waitForHealth(
        signal,
        options.healthPollIntervalMs ?? 20,
        options.healthTimeoutMs ?? 5_000,
      );
    } catch (error) {
      if (error instanceof RuntimeVersionIncompatibleError) {
        return {
          kind: "incompatible",
          runtime: ManagedRuntimeState.incompatible(error.installedVersion, error.requiredRange),
          spawned: true,
        };
      }
      throw error;
    }

    return {
      kind: "ready",
      runtime: ManagedRuntimeState.running(health.version),
      connection,
      ownership: "owned",
      spawned: true,
    };
  }

  private async probeHealth(
    signal?: AbortSignal,
  ): Promise<
    | { readonly kind: "ready"; readonly health: HealthInfo }
    | { readonly kind: "unavailable" }
    | { readonly kind: "incompatible"; readonly error: RuntimeVersionIncompatibleError }
  > {
    try {
      return { kind: "ready", health: await this.rag.health(signal) };
    } catch (error) {
      if (error instanceof RuntimeVersionIncompatibleError) {
        return { kind: "incompatible", error };
      }
      if (isAbortError(error)) {
        throw error;
      }
      return { kind: "unavailable" };
    }
  }

  private async waitForHealth(
    signal: AbortSignal | undefined,
    intervalMs: number,
    timeoutMs: number,
  ): Promise<HealthInfo> {
    const deadline = this.clock.now().getTime() + timeoutMs;
    for (;;) {
      if (signal?.aborted) {
        throw new DOMException("The operation was aborted", "AbortError");
      }
      try {
        return await this.rag.health(signal);
      } catch (error) {
        if (isAbortError(error)) {
          throw error;
        }
        if (error instanceof RuntimeVersionIncompatibleError) {
          throw error;
        }
        if (this.clock.now().getTime() >= deadline) {
          throw error;
        }
        await this.clock.sleep(intervalMs, signal);
      }
    }
  }
}
