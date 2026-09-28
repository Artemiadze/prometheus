import type { StartRuntime } from "../application/use-cases/StartRuntime";

export type RuntimeReadiness =
  { readonly ok: true } | { readonly ok: false; readonly message: string };

/**
 * Shared lazy StartRuntime probe for chat and search panels.
 */
export function createEnsureRuntime(
  startRuntime: Pick<StartRuntime, "execute">,
): (signal: AbortSignal) => Promise<RuntimeReadiness> {
  return async (signal) => {
    const result = await startRuntime.execute(signal);
    switch (result.kind) {
      case "ready":
        return { ok: true };
      case "missing":
        return {
          ok: false,
          message: "Prometheus runtime is not installed. Install it from the status panel.",
        };
      case "incompatible":
        return {
          ok: false,
          message: "Prometheus runtime version is incompatible. Update the sidecar.",
        };
      default: {
        const _exhaustive: never = result;
        return _exhaustive;
      }
    }
  };
}
