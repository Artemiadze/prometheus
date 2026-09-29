import type { StartRuntime } from "../application/use-cases/StartRuntime";
import { presentError } from "../adapters/inbound/obsidian/errors/presentError";
import { RuntimeNotInstalledError, RuntimeVersionIncompatibleError } from "../domain/errors";

export type RuntimeReadiness =
  { readonly ok: true } | { readonly ok: false; readonly message: string };

/**
 * Shared lazy StartRuntime probe for chat and search panels.
 */
export function createEnsureRuntime(
  startRuntime: Pick<StartRuntime, "execute">,
  onActivated?: () => void,
): (signal: AbortSignal) => Promise<RuntimeReadiness> {
  return async (signal) => {
    const result = await startRuntime.execute(signal);
    switch (result.kind) {
      case "ready":
        onActivated?.();
        return { ok: true };
      case "missing":
        return {
          ok: false,
          message: presentError(new RuntimeNotInstalledError()).message,
        };
      case "incompatible": {
        const runtime = result.runtime;
        const installed = runtime.kind === "incompatible" ? runtime.installedVersion : "unknown";
        const required = runtime.kind === "incompatible" ? runtime.requiredRange : "unknown";
        return {
          ok: false,
          message: presentError(new RuntimeVersionIncompatibleError(installed, required)).message,
        };
      }
      default: {
        const _exhaustive: never = result;
        return _exhaustive;
      }
    }
  };
}
