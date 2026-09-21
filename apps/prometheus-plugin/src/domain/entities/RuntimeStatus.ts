export type RuntimeRecommendedAction = "download" | "wait" | "updatePlugin" | "none" | "restart";

export type ManagedRuntimeState =
  | { readonly kind: "missing" }
  | { readonly kind: "downloading"; readonly progressPercent: number }
  | { readonly kind: "verifying" }
  | {
      readonly kind: "incompatible";
      readonly installedVersion: string;
      readonly requiredRange: string;
    }
  | { readonly kind: "starting" }
  | { readonly kind: "running"; readonly version: string }
  | { readonly kind: "stopped" };

export type OllamaState =
  { readonly kind: "notInstalled" } | { readonly kind: "stopped" } | { readonly kind: "running" };

export type SelectedModel = {
  readonly name: string;
  readonly installed: boolean;
};

export type RuntimeStatus = {
  readonly runtime: ManagedRuntimeState;
  readonly ollama: OllamaState;
  readonly selectedModel: SelectedModel | null;
};

export const ManagedRuntimeState = {
  missing(): ManagedRuntimeState {
    return { kind: "missing" };
  },
  downloading(progressPercent: number): ManagedRuntimeState {
    return { kind: "downloading", progressPercent };
  },
  verifying(): ManagedRuntimeState {
    return { kind: "verifying" };
  },
  incompatible(installedVersion: string, requiredRange: string): ManagedRuntimeState {
    return { kind: "incompatible", installedVersion, requiredRange };
  },
  starting(): ManagedRuntimeState {
    return { kind: "starting" };
  },
  running(version: string): ManagedRuntimeState {
    return { kind: "running", version };
  },
  stopped(): ManagedRuntimeState {
    return { kind: "stopped" };
  },
};

export const OllamaState = {
  notInstalled(): OllamaState {
    return { kind: "notInstalled" };
  },
  stopped(): OllamaState {
    return { kind: "stopped" };
  },
  running(): OllamaState {
    return { kind: "running" };
  },
};

export function createRuntimeStatus(input: {
  runtime: ManagedRuntimeState;
  ollama: OllamaState;
  selectedModel?: SelectedModel | null;
}): RuntimeStatus {
  return {
    runtime: input.runtime,
    ollama: input.ollama,
    selectedModel: input.selectedModel ?? null,
  };
}

export function recommendedActionForRuntime(state: ManagedRuntimeState): RuntimeRecommendedAction {
  switch (state.kind) {
    case "missing":
      return "download";
    case "downloading":
    case "verifying":
    case "starting":
      return "wait";
    case "incompatible":
      return "updatePlugin";
    case "running":
      return "none";
    case "stopped":
      return "restart";
    default: {
      const _exhaustive: never = state;
      return _exhaustive;
    }
  }
}

/** Representative happy-path transition sequence for status UI tests. */
export function transitionRuntimeToRunning(
  from: ManagedRuntimeState,
  version: string,
): ManagedRuntimeState[] {
  switch (from.kind) {
    case "missing":
      return [
        ManagedRuntimeState.missing(),
        ManagedRuntimeState.downloading(0),
        ManagedRuntimeState.verifying(),
        ManagedRuntimeState.starting(),
        ManagedRuntimeState.running(version),
      ];
    case "stopped":
      return [
        ManagedRuntimeState.stopped(),
        ManagedRuntimeState.starting(),
        ManagedRuntimeState.running(version),
      ];
    default:
      return [from, ManagedRuntimeState.running(version)];
  }
}
