export type RuntimeMode = "managed" | "custom";

export type NetworkAccessMode = "updates_only" | "disabled";

export type NoteOpenMode = "reuse_active" | "open_new_pane";

/** UI-selectable search scopes (selected_folders is API-only for now). */
export type SearchScopePreference = "entire_vault" | "current_folder" | "current_note";

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
  readonly noteOpenMode: NoteOpenMode;
  readonly indexingDebounceMs: number;
  readonly maxConcurrentSyncs: number;
  readonly searchScopeMode: SearchScopePreference;
  readonly applySearchScopeToChat: boolean;
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
};

/** Always ignored regardless of user settings. */
export const SYSTEM_IGNORED_FOLDERS: readonly string[] = [".obsidian/"];
