import type { StatusViewState } from "../status/StatusStore";

export function canReindexVault(state: StatusViewState): boolean {
  if (state.actionBusy || state.status === null) {
    return false;
  }
  return state.indexAction !== "wait";
}

export function canRestartRuntime(state: StatusViewState): boolean {
  if (state.actionBusy || state.status === null) {
    return false;
  }
  const kind = state.status.runtime.runtime.kind;
  return kind === "running" || kind === "stopped";
}
