import {
  ManagedRuntimeState,
  type ManagedRuntimeState as ManagedRuntimeStateType,
} from "../../domain/entities/RuntimeStatus";
import type { Clock } from "../ports/Clock";
import type { RagGateway } from "../ports/RagGateway";
import type { RuntimeConnection, RuntimeGateway } from "../ports/RuntimeGateway";
import type { SettingsRepository } from "../ports/SettingsRepository";
import type { RuntimeSessionRegistry } from "../services/RuntimeSessionRegistry";
import { isAbortError } from "../../domain/errors";

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

    if (await this.probeHealth(signal)) {
      const existing = this.sessions.get()?.connection ?? EXTERNAL_CONNECTION;
      this.sessions.set({ connection: existing, ownership: "external" });
      return {
        kind: "ready",
        runtime: ManagedRuntimeState.running(
          (await this.runtime.getInstalledVersion()) ?? "unknown",
        ),
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

    await this.waitForHealth(
      signal,
      options.healthPollIntervalMs ?? 20,
      options.healthTimeoutMs ?? 5_000,
    );

    return {
      kind: "ready",
      runtime: ManagedRuntimeState.running((await this.runtime.getInstalledVersion()) ?? "0.1.0"),
      connection,
      ownership: "owned",
      spawned: true,
    };
  }

  private async probeHealth(signal?: AbortSignal): Promise<boolean> {
    try {
      await this.rag.health(signal);
      return true;
    } catch {
      return false;
    }
  }

  private async waitForHealth(
    signal: AbortSignal | undefined,
    intervalMs: number,
    timeoutMs: number,
  ): Promise<void> {
    const deadline = this.clock.now().getTime() + timeoutMs;
    for (;;) {
      if (signal?.aborted) {
        throw new DOMException("The operation was aborted", "AbortError");
      }
      try {
        await this.rag.health(signal);
        return;
      } catch (error) {
        if (isAbortError(error)) {
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
