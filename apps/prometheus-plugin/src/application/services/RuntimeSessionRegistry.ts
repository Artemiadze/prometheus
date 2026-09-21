import type { RuntimeConnection } from "../ports/RuntimeGateway";

export type SessionOwnership = "owned" | "external";

export type RuntimeSession = {
  readonly connection: RuntimeConnection;
  readonly ownership: SessionOwnership;
};

/**
 * Tracks the active runtime connection and whether this plugin instance spawned it.
 * Session tokens must never be logged or shown in notifier messages.
 */
export class RuntimeSessionRegistry {
  private session: RuntimeSession | null = null;

  get(): RuntimeSession | null {
    return this.session;
  }

  set(session: RuntimeSession): void {
    this.session = session;
  }

  clear(): void {
    this.session = null;
  }

  isOwned(): boolean {
    return this.session?.ownership === "owned";
  }
}
