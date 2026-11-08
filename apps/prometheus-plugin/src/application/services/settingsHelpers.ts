import { VaultId } from "../../domain/value-objects/VaultId";
import type { PluginSettings } from "../dto/settings";
import { InvariantViolationError } from "../../domain/errors";

export function requireVaultId(settings: PluginSettings): VaultId {
  if (!settings.vaultId) {
    throw new InvariantViolationError();
  }
  return VaultId.create(settings.vaultId);
}

/** Normalize Vault#configDir to a trailing-slash folder prefix for ignore matching. */
export function normalizeConfigDirPrefix(configDir: string): string {
  const normalized = configDir.trim().replace(/\\/g, "/").replace(/^\.\//, "");
  if (normalized.length === 0) {
    return "";
  }
  return normalized.endsWith("/") ? normalized : `${normalized}/`;
}

/**
 * Effective ignore list: vault config dir (from Vault#configDir) plus user folders.
 */
export function effectiveIgnoredFolders(
  settings: PluginSettings,
  configDir: string,
): readonly string[] {
  const system = normalizeConfigDirPrefix(configDir);
  return system.length > 0 ? [system, ...settings.ignoredFolders] : [...settings.ignoredFolders];
}

export function isIgnoredPath(pathValue: string, ignoredFolders: readonly string[]): boolean {
  return ignoredFolders.some((folder) => {
    const normalized = folder.replace(/\\/g, "/");
    const prefix = normalized.endsWith("/") ? normalized : `${normalized}/`;
    const bare = prefix.slice(0, -1);
    return pathValue === bare || pathValue.startsWith(prefix);
  });
}
