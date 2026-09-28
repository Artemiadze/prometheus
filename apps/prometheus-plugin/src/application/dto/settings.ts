export type RuntimeMode = "managed" | "custom";

export type NetworkAccessMode = "updates_only" | "disabled";

export type NoteOpenMode = "reuse_active" | "open_new_pane";

/** UI-selectable search scopes (selected_folders is API-only for now). */
export type SearchScopePreference = "entire_vault" | "current_folder" | "current_note";

/**
 * Plugin-owned settings persisted in Obsidian data.json (Project_analytics §48).
 * Chunk size / LLM temperature / context size are local-only until the runtime
 * exposes a config surface; they do not yet change sidecar behaviour.
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
  readonly noteOpenMode: NoteOpenMode;
  readonly indexingDebounceMs: number;
  readonly maxConcurrentSyncs: number;
  readonly searchScopeMode: SearchScopePreference;
  readonly applySearchScopeToChat: boolean;
  readonly hasCompletedOnboarding: boolean;
  /** Local-only preference; runtime chunking not yet configurable via plugin. */
  readonly chunkSizeTokens: number;
  /** Local-only preference; runtime chunking not yet configurable via plugin. */
  readonly chunkOverlapTokens: number;
  /** Local-only preference; runtime LLM params not yet configurable via plugin. */
  readonly llmTemperature: number;
  /** Local-only preference; runtime LLM params not yet configurable via plugin. */
  readonly llmContextSize: number;
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
  noteOpenMode: "reuse_active",
  indexingDebounceMs: 750,
  maxConcurrentSyncs: 2,
  searchScopeMode: "entire_vault",
  applySearchScopeToChat: false,
  hasCompletedOnboarding: false,
  chunkSizeTokens: 700,
  chunkOverlapTokens: 80,
  llmTemperature: 0.2,
  llmContextSize: 4096,
};

/** Always ignored regardless of user settings. */
export const SYSTEM_IGNORED_FOLDERS: readonly string[] = [".obsidian/"];
