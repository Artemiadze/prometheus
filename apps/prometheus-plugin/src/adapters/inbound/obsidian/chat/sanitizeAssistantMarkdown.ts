/**
 * Escapes raw HTML tags outside fenced and inline code so MarkdownRenderer
 * never receives unescaped HTML from the model, and turns single newlines into
 * markdown hard breaks so line breaks from the model stay visible.
 */
export function sanitizeAssistantMarkdown(text: string): string {
  const normalized = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const segments = splitCodeSegments(normalized);
  return segments
    .map((segment) =>
      segment.kind === "code"
        ? segment.value
        : preserveSingleNewlines(escapeHtmlTags(segment.value)),
    )
    .join("");
}

type Segment = { readonly kind: "text" | "code"; readonly value: string };

function splitCodeSegments(text: string): Segment[] {
  const segments: Segment[] = [];
  const fencePattern = /(```[\s\S]*?```|`[^`\n]+`)/g;
  let lastIndex = 0;
  for (const match of text.matchAll(fencePattern)) {
    const index = match.index ?? 0;
    if (index > lastIndex) {
      segments.push({ kind: "text", value: text.slice(lastIndex, index) });
    }
    segments.push({ kind: "code", value: match[0] ?? "" });
    lastIndex = index + (match[0]?.length ?? 0);
  }
  if (lastIndex < text.length) {
    segments.push({ kind: "text", value: text.slice(lastIndex) });
  }
  return segments.length > 0 ? segments : [{ kind: "text", value: text }];
}

function escapeHtmlTags(text: string): string {
  return text.replace(/<\/?[a-zA-Z][^>]*>/g, (tag) =>
    tag.replace(/</g, "&lt;").replace(/>/g, "&gt;"),
  );
}

/** Markdown hard break: two trailing spaces before a lone newline (not a blank line). */
function preserveSingleNewlines(text: string): string {
  return text.replace(/([^\n])\n(?!\n)/g, "$1  \n");
}
