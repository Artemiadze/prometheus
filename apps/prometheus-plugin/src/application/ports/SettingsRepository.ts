import type { PluginSettings } from "../dto/settings";

/** Read/write plugin settings (Obsidian data.json behind the adapter). */
export interface SettingsRepository {
  get(): Promise<PluginSettings>;
  save(settings: PluginSettings): Promise<void>;
}
