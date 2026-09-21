import { DEFAULT_PLUGIN_SETTINGS, type PluginSettings } from "../../src/application/dto/settings";
import type { SettingsRepository } from "../../src/application/ports/SettingsRepository";

export class FakeSettingsRepository implements SettingsRepository {
  private settings: PluginSettings;

  constructor(initial: PluginSettings = DEFAULT_PLUGIN_SETTINGS) {
    this.settings = cloneSettings(initial);
  }

  async get(): Promise<PluginSettings> {
    return cloneSettings(this.settings);
  }

  async save(settings: PluginSettings): Promise<void> {
    this.settings = cloneSettings(settings);
  }
}

function cloneSettings(settings: PluginSettings): PluginSettings {
  return {
    ...settings,
    ignoredFolders: [...settings.ignoredFolders],
  };
}
