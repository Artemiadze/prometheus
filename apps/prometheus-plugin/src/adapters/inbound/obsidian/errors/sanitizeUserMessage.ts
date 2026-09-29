/**
 * Strip stack traces and absolute filesystem paths from user-facing text.
 * Vault-relative note paths are left intact.
 */
export function sanitizeUserMessage(raw: string): string {
  const withoutStack = raw
    .split(/\r?\n/)
    .filter((line) => !isStackFrame(line))
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();

  return withoutStack
    .replace(/\b[A-Za-z]:\\[^\s]+/g, "[path]")
    .replace(/(^|[\s("'=])(\/(?:home|Users|tmp|var|opt|usr|root)\/[^\s"')]+)/g, "$1[path]")
    .replace(/(^|[\s("'=])(\/(?:[^\s/"')]+\/)+[^\s"')]+)/g, (match, prefix, path) => {
      // Keep short vault-relative looking segments; redact long absolute paths.
      if (typeof path === "string" && path.split("/").length >= 4) {
        return `${prefix}[path]`;
      }
      return match;
    });
}

function isStackFrame(line: string): boolean {
  const trimmed = line.trim();
  return (
    trimmed.startsWith("at ") ||
    trimmed.startsWith("Error:") ||
    /^\s*at\s+/.test(line) ||
    /:\d+:\d+\)?$/.test(trimmed)
  );
}
