export type RuntimeMode = "managed" | "custom";

export type NetworkAccessMode = "updates_only" | "disabled";

/**
 * Plugin-owned settings persisted in Obsidian data.json (Project_analytics §48).
 * Embedding/chunk size live in the runtime, not here.
 */
export type PluginSettings = {
  readonly runtimeMode: RuntimeMode;
  readonly customBinaryPath: string | null;
  readonly autoIndexing: boolean;
  readonly ignoredFolders: readonly string[];
  readonly llmModel: string;
  readonly ollamaAddress: string;
  readonly networkAccess: NetworkAccessMode;
  readonly vaultId: string | null;
};

export const DEFAULT_PLUGIN_SETTINGS: PluginSettings = {
  runtimeMode: "managed",
  customBinaryPath: null,
  autoIndexing: true,
  ignoredFolders: [".attachments/", "Templates/"],
  llmModel: "qwen3:4b",
  ollamaAddress: "127.0.0.1:11434",
  networkAccess: "updates_only",
  vaultId: null,
};
