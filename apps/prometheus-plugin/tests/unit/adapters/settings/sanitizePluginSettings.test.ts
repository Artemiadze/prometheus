import { describe, expect, it } from "vitest";

import { sanitizePluginSettings } from "../../../../src/adapters/outbound/settings/sanitizePluginSettings";
import { DEFAULT_PLUGIN_SETTINGS } from "../../../../src/application/dto/settings";

describe("sanitizePluginSettings", () => {
  it("returns defaults for empty input", () => {
    const result = sanitizePluginSettings(null);
    expect(result.settings).toEqual(DEFAULT_PLUGIN_SETTINGS);
    expect(result.corrections).toEqual([]);
  });

  it("keeps valid values", () => {
    const result = sanitizePluginSettings({
      ...DEFAULT_PLUGIN_SETTINGS,
      runtimeMode: "custom",
      chunkSizeTokens: 512,
      llmTemperature: 0.5,
    });
    expect(result.settings.runtimeMode).toBe("custom");
    expect(result.settings.chunkSizeTokens).toBe(512);
    expect(result.settings.llmTemperature).toBe(0.5);
    expect(result.corrections).toEqual([]);
  });

  it("corrects invalid enums and numbers", () => {
    const result = sanitizePluginSettings({
      runtimeMode: "cloud",
      networkAccess: "open",
      indexingDebounceMs: -1,
      maxConcurrentSyncs: 1.5,
      chunkSizeTokens: 0,
      llmTemperature: 9,
      ignoredFolders: "not-an-array",
      autoIndexing: "yes",
    });
    expect(result.settings.runtimeMode).toBe("managed");
    expect(result.settings.networkAccess).toBe("updates_only");
    expect(result.settings.indexingDebounceMs).toBe(DEFAULT_PLUGIN_SETTINGS.indexingDebounceMs);
    expect(result.settings.maxConcurrentSyncs).toBe(DEFAULT_PLUGIN_SETTINGS.maxConcurrentSyncs);
    expect(result.settings.chunkSizeTokens).toBe(DEFAULT_PLUGIN_SETTINGS.chunkSizeTokens);
    expect(result.settings.llmTemperature).toBe(DEFAULT_PLUGIN_SETTINGS.llmTemperature);
    expect(result.settings.ignoredFolders).toEqual(DEFAULT_PLUGIN_SETTINGS.ignoredFolders);
    expect(result.settings.autoIndexing).toBe(true);
    expect(result.corrections.length).toBeGreaterThan(3);
  });
});
