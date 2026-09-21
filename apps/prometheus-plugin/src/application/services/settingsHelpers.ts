import { VaultId } from "../../domain/value-objects/VaultId";
import { SYSTEM_IGNORED_FOLDERS, type PluginSettings } from "../dto/settings";
import { InvariantViolationError } from "../../domain/errors";

export function requireVaultId(settings: PluginSettings): VaultId {
  if (!settings.vaultId) {
    throw new InvariantViolationError();
  }
  return VaultId.create(settings.vaultId);
}

export function effectiveIgnoredFolders(settings: PluginSettings): readonly string[] {
  return [...SYSTEM_IGNORED_FOLDERS, ...settings.ignoredFolders];
}

export function isIgnoredPath(pathValue: string, ignoredFolders: readonly string[]): boolean {
  return ignoredFolders.some((folder) => {
    const normalized = folder.replace(/\\/g, "/");
    const prefix = normalized.endsWith("/") ? normalized : `${normalized}/`;
    const bare = prefix.slice(0, -1);
    return pathValue === bare || pathValue.startsWith(prefix);
  });
}
