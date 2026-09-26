/**
 * Escapes raw HTML tags outside fenced and inline code so MarkdownRenderer
 * never receives unescaped HTML from the model.
 */
export function sanitizeAssistantMarkdown(text: string): string {
  const segments = splitCodeSegments(text);
  return segments
    .map((segment) => (segment.kind === "code" ? segment.value : escapeHtmlTags(segment.value)))
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
