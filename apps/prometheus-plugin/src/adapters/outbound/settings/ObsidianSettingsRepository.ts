import { DEFAULT_PLUGIN_SETTINGS, type PluginSettings } from "../../../application/dto/settings";
import type { Notifier } from "../../../application/ports/Notifier";
import type { SettingsRepository } from "../../../application/ports/SettingsRepository";
import { VaultId } from "../../../domain/value-objects/VaultId";
import { sanitizePluginSettings } from "./sanitizePluginSettings";

/**
 * Obsidian data.json settings adapter (vaultId + shared PluginSettings).
 * Invalid values are replaced with defaults and surfaced via Notifier.
 */
export class ObsidianSettingsRepository implements SettingsRepository {
  private readonly notifier: Notifier | null;
  private warnedAboutCorrections = false;

  constructor(
    private readonly plugin: DataPlugin,
    notifier?: Notifier,
  ) {
    this.notifier = notifier ?? null;
  }

  async get(): Promise<PluginSettings> {
    const raw = await this.plugin.loadData();
    const { settings, corrections } = sanitizePluginSettings(raw);
    if (corrections.length > 0 && this.notifier && !this.warnedAboutCorrections) {
      this.warnedAboutCorrections = true;
      this.notifier.warning(`Prometheus settings were corrected: ${corrections.join("; ")}.`);
    }
    return settings;
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

/**
 * @deprecated Prefer sanitizePluginSettings for correction tracking.
 * Kept for callers that only need a merged PluginSettings object.
 */
export function mergeSettings(raw: Partial<PluginSettings> | null | undefined): PluginSettings {
  return sanitizePluginSettings(raw ?? DEFAULT_PLUGIN_SETTINGS).settings;
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
