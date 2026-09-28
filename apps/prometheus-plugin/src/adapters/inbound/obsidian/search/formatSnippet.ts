/**
 * Convert Markdown fragment text into a plain snippet and truncate on a word boundary.
 */
export function toPlainSnippet(text: string, maxLength = 240): string {
  let plain = text;
  plain = plain.replace(/```[\s\S]*?```/g, " ");
  plain = plain.replace(/`([^`]+)`/g, "$1");
  plain = plain.replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, "$2");
  plain = plain.replace(/\[\[([^\]]+)\]\]/g, "$1");
  plain = plain.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
  plain = plain.replace(/^#{1,6}\s+/gm, "");
  plain = plain.replace(/(\*\*|__)(.*?)\1/g, "$2");
  plain = plain.replace(/(\*|_)(.*?)\1/g, "$2");
  plain = plain.replace(/\s+/g, " ").trim();

  if (plain.length <= maxLength) {
    return plain;
  }
  const truncated = plain.slice(0, maxLength);
  const lastSpace = truncated.lastIndexOf(" ");
  const cut = lastSpace > maxLength * 0.6 ? truncated.slice(0, lastSpace) : truncated;
  return `${cut.trimEnd()}…`;
}
