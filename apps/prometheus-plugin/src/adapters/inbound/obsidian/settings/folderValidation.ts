/**
 * Pure folder-path validation helpers for the Indexing settings section.
 * Obsidian folder existence is checked by the caller via a boolean predicate.
 */

export type FolderValidationResult =
  | { readonly ok: true; readonly normalized: string }
  | { readonly ok: false; readonly message: string };

export function normalizeIgnoredFolderPath(raw: string): string {
  let value = raw.trim().replace(/\\/g, "/");
  while (value.startsWith("./")) {
    value = value.slice(2);
  }
  if (value.startsWith("/")) {
    value = value.slice(1);
  }
  if (value.length > 0 && !value.endsWith("/")) {
    value = `${value}/`;
  }
  return value;
}

export function validateIgnoredFolderPath(
  raw: string,
  folderExists: (normalizedPath: string) => boolean,
): FolderValidationResult {
  const normalized = normalizeIgnoredFolderPath(raw);
  if (normalized.length === 0) {
    return { ok: false, message: "Folder path cannot be empty." };
  }
  if (normalized.includes("..")) {
    return { ok: false, message: "Folder path must stay inside the vault." };
  }
  const bare = normalized.endsWith("/") ? normalized.slice(0, -1) : normalized;
  if (!folderExists(bare) && !folderExists(normalized)) {
    return { ok: false, message: `Folder does not exist: ${bare}` };
  }
  return { ok: true, normalized };
}
