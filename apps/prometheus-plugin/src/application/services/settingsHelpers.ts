import { VaultId } from "../../domain/value-objects/VaultId";
import type { PluginSettings } from "../dto/settings";
import { InvariantViolationError } from "../../domain/errors";

export function requireVaultId(settings: PluginSettings): VaultId {
  if (!settings.vaultId) {
    throw new InvariantViolationError();
  }
  return VaultId.create(settings.vaultId);
}

export function isIgnoredPath(pathValue: string, ignoredFolders: readonly string[]): boolean {
  return ignoredFolders.some((folder) => {
    const prefix = folder.endsWith("/") ? folder : `${folder}/`;
    return pathValue === folder.replace(/\/$/, "") || pathValue.startsWith(prefix);
  });
}
