import {
  DEFAULT_PLUGIN_SETTINGS,
  type NetworkAccessMode,
  type NoteOpenMode,
  type PluginSettings,
  type RuntimeMode,
  type SearchScopePreference,
} from "../../../application/dto/settings";

export type SanitizeResult = {
  readonly settings: PluginSettings;
  readonly corrections: readonly string[];
};

const RUNTIME_MODES: ReadonlySet<string> = new Set(["managed", "custom"]);
const NETWORK_MODES: ReadonlySet<string> = new Set(["updates_only", "disabled"]);
const NOTE_OPEN_MODES: ReadonlySet<string> = new Set(["reuse_active", "open_new_pane"]);
const SEARCH_SCOPE_MODES: ReadonlySet<string> = new Set([
  "entire_vault",
  "current_folder",
  "current_note",
]);

/**
 * Coerce unknown/partial data.json payloads into a valid PluginSettings.
 * Invalid fields are replaced with defaults and listed in `corrections`.
 */
export function sanitizePluginSettings(raw: unknown): SanitizeResult {
  const corrections: string[] = [];
  const source =
    raw !== null && typeof raw === "object" && !Array.isArray(raw)
      ? (raw as Record<string, unknown>)
      : {};

  const runtimeMode = pickEnum(
    source.runtimeMode,
    RUNTIME_MODES,
    DEFAULT_PLUGIN_SETTINGS.runtimeMode,
    "runtimeMode",
    corrections,
  ) as RuntimeMode;

  const networkAccess = pickEnum(
    source.networkAccess,
    NETWORK_MODES,
    DEFAULT_PLUGIN_SETTINGS.networkAccess,
    "networkAccess",
    corrections,
  ) as NetworkAccessMode;

  const noteOpenMode = pickEnum(
    source.noteOpenMode,
    NOTE_OPEN_MODES,
    DEFAULT_PLUGIN_SETTINGS.noteOpenMode,
    "noteOpenMode",
    corrections,
  ) as NoteOpenMode;

  const searchScopeMode = pickEnum(
    source.searchScopeMode,
    SEARCH_SCOPE_MODES,
    DEFAULT_PLUGIN_SETTINGS.searchScopeMode,
    "searchScopeMode",
    corrections,
  ) as SearchScopePreference;

  const customBinaryPath = pickNullableString(
    source.customBinaryPath,
    DEFAULT_PLUGIN_SETTINGS.customBinaryPath,
    "customBinaryPath",
    corrections,
  );

  const ignoredFolders = pickStringArray(
    source.ignoredFolders,
    DEFAULT_PLUGIN_SETTINGS.ignoredFolders,
    "ignoredFolders",
    corrections,
  );

  const vaultId = pickNullableString(
    source.vaultId,
    DEFAULT_PLUGIN_SETTINGS.vaultId,
    "vaultId",
    corrections,
  );

  const settings: PluginSettings = {
    runtimeMode,
    customBinaryPath,
    autoIndexing: pickBoolean(
      source.autoIndexing,
      DEFAULT_PLUGIN_SETTINGS.autoIndexing,
      "autoIndexing",
      corrections,
    ),
    ignoredFolders,
    llmModel: pickNonEmptyString(
      source.llmModel,
      DEFAULT_PLUGIN_SETTINGS.llmModel,
      "llmModel",
      corrections,
    ),
    ollamaAddress: pickNonEmptyString(
      source.ollamaAddress,
      DEFAULT_PLUGIN_SETTINGS.ollamaAddress,
      "ollamaAddress",
      corrections,
    ),
    networkAccess,
    vaultId,
    noteOpenMode,
    indexingDebounceMs: pickPositiveNumber(
      source.indexingDebounceMs,
      DEFAULT_PLUGIN_SETTINGS.indexingDebounceMs,
      "indexingDebounceMs",
      corrections,
    ),
    maxConcurrentSyncs: pickPositiveInteger(
      source.maxConcurrentSyncs,
      DEFAULT_PLUGIN_SETTINGS.maxConcurrentSyncs,
      "maxConcurrentSyncs",
      corrections,
    ),
    searchScopeMode,
    applySearchScopeToChat: pickBoolean(
      source.applySearchScopeToChat,
      DEFAULT_PLUGIN_SETTINGS.applySearchScopeToChat,
      "applySearchScopeToChat",
      corrections,
    ),
    hasCompletedOnboarding: pickBoolean(
      source.hasCompletedOnboarding,
      DEFAULT_PLUGIN_SETTINGS.hasCompletedOnboarding,
      "hasCompletedOnboarding",
      corrections,
    ),
    chunkSizeTokens: pickPositiveInteger(
      source.chunkSizeTokens,
      DEFAULT_PLUGIN_SETTINGS.chunkSizeTokens,
      "chunkSizeTokens",
      corrections,
    ),
    chunkOverlapTokens: pickNonNegativeInteger(
      source.chunkOverlapTokens,
      DEFAULT_PLUGIN_SETTINGS.chunkOverlapTokens,
      "chunkOverlapTokens",
      corrections,
    ),
    llmTemperature: pickFiniteNumber(
      source.llmTemperature,
      DEFAULT_PLUGIN_SETTINGS.llmTemperature,
      "llmTemperature",
      corrections,
      0,
      2,
    ),
    llmContextSize: pickPositiveInteger(
      source.llmContextSize,
      DEFAULT_PLUGIN_SETTINGS.llmContextSize,
      "llmContextSize",
      corrections,
    ),
    verboseLogging: pickBoolean(
      source.verboseLogging,
      DEFAULT_PLUGIN_SETTINGS.verboseLogging,
      "verboseLogging",
      corrections,
    ),
  };

  return { settings, corrections };
}

function pickEnum(
  value: unknown,
  allowed: ReadonlySet<string>,
  fallback: string,
  field: string,
  corrections: string[],
): string {
  if (typeof value === "string" && allowed.has(value)) {
    return value;
  }
  if (value !== undefined) {
    corrections.push(`${field} was invalid and reset to default`);
  }
  return fallback;
}

function pickBoolean(
  value: unknown,
  fallback: boolean,
  field: string,
  corrections: string[],
): boolean {
  if (typeof value === "boolean") {
    return value;
  }
  if (value !== undefined) {
    corrections.push(`${field} was invalid and reset to default`);
  }
  return fallback;
}

function pickNonEmptyString(
  value: unknown,
  fallback: string,
  field: string,
  corrections: string[],
): string {
  if (typeof value === "string" && value.trim().length > 0) {
    return value;
  }
  if (value !== undefined) {
    corrections.push(`${field} was invalid and reset to default`);
  }
  return fallback;
}

function pickNullableString(
  value: unknown,
  fallback: string | null,
  field: string,
  corrections: string[],
): string | null {
  if (value === null || value === undefined) {
    return value === undefined ? fallback : null;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
  }
  corrections.push(`${field} was invalid and reset to default`);
  return fallback;
}

function pickStringArray(
  value: unknown,
  fallback: readonly string[],
  field: string,
  corrections: string[],
): readonly string[] {
  if (Array.isArray(value) && value.every((item) => typeof item === "string")) {
    return [...value];
  }
  if (value !== undefined) {
    corrections.push(`${field} was invalid and reset to default`);
  }
  return [...fallback];
}

function pickPositiveNumber(
  value: unknown,
  fallback: number,
  field: string,
  corrections: string[],
): number {
  if (typeof value === "number" && Number.isFinite(value) && value > 0) {
    return value;
  }
  if (value !== undefined) {
    corrections.push(`${field} was invalid and reset to default`);
  }
  return fallback;
}

function pickPositiveInteger(
  value: unknown,
  fallback: number,
  field: string,
  corrections: string[],
): number {
  if (typeof value === "number" && Number.isFinite(value) && value > 0 && Number.isInteger(value)) {
    return value;
  }
  if (value !== undefined) {
    corrections.push(`${field} was invalid and reset to default`);
  }
  return fallback;
}

function pickNonNegativeInteger(
  value: unknown,
  fallback: number,
  field: string,
  corrections: string[],
): number {
  if (
    typeof value === "number" &&
    Number.isFinite(value) &&
    value >= 0 &&
    Number.isInteger(value)
  ) {
    return value;
  }
  if (value !== undefined) {
    corrections.push(`${field} was invalid and reset to default`);
  }
  return fallback;
}

function pickFiniteNumber(
  value: unknown,
  fallback: number,
  field: string,
  corrections: string[],
  min: number,
  max: number,
): number {
  if (typeof value === "number" && Number.isFinite(value) && value >= min && value <= max) {
    return value;
  }
  if (value !== undefined) {
    corrections.push(`${field} was invalid and reset to default`);
  }
  return fallback;
}
