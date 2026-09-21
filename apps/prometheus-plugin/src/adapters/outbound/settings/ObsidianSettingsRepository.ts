import { DEFAULT_PLUGIN_SETTINGS, type PluginSettings } from "../../../application/dto/settings";
import type { SettingsRepository } from "../../../application/ports/SettingsRepository";
import { VaultId } from "../../../domain/value-objects/VaultId";

/**
 * Minimal Obsidian data.json settings adapter (vaultId + shared PluginSettings).
 */
export class ObsidianSettingsRepository implements SettingsRepository {
  constructor(private readonly plugin: DataPlugin) {}

  async get(): Promise<PluginSettings> {
    const raw = (await this.plugin.loadData()) as Partial<PluginSettings> | null;
    return mergeSettings(raw);
  }

  async save(settings: PluginSettings): Promise<void> {
    await this.plugin.saveData({ ...settings, ignoredFolders: [...settings.ignoredFolders] });
  }
}

/** Narrow Plugin surface used by the settings adapter (avoids coupling to full Plugin type). */
export type DataPlugin = {
  loadData(): Promise<unknown>;
  saveData(data: unknown): Promise<void>;
};

export function mergeSettings(raw: Partial<PluginSettings> | null | undefined): PluginSettings {
  return {
    ...DEFAULT_PLUGIN_SETTINGS,
    ...raw,
    ignoredFolders: raw?.ignoredFolders
      ? [...raw.ignoredFolders]
      : [...DEFAULT_PLUGIN_SETTINGS.ignoredFolders],
    indexingDebounceMs: raw?.indexingDebounceMs ?? DEFAULT_PLUGIN_SETTINGS.indexingDebounceMs,
    maxConcurrentSyncs: raw?.maxConcurrentSyncs ?? DEFAULT_PLUGIN_SETTINGS.maxConcurrentSyncs,
  };
}

/**
 * Cryptographically random VaultId — never derived from vault path/name.
 * Format: `v` + 16 hex chars (matches VaultId regex).
 */
export function generateVaultId(): string {
  const bytes = new Uint8Array(8);
  crypto.getRandomValues(bytes);
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return VaultId.create(`v${hex}`).value;
}

/**
 * Persist a VaultId once if missing. Call from bootstrap/onload.
 */
export async function ensureVaultId(settingsRepo: SettingsRepository): Promise<string> {
  const settings = await settingsRepo.get();
  if (settings.vaultId) {
    return VaultId.create(settings.vaultId).value;
  }
  const vaultId = generateVaultId();
  await settingsRepo.save({ ...settings, vaultId });
  return vaultId;
}
