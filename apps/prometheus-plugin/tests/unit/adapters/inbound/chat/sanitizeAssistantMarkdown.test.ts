import { describe, expect, it } from "vitest";

import { sanitizeAssistantMarkdown } from "../../../../../src/adapters/inbound/obsidian/chat/sanitizeAssistantMarkdown";

describe("sanitizeAssistantMarkdown", () => {
  it("escapes raw HTML outside code", () => {
    expect(sanitizeAssistantMarkdown("<script>alert(1)</script>")).toContain("&lt;script&gt;");
  });

  it("preserves fenced code blocks", () => {
    const input = "`<div>ok</div>` and ```html\n<div>safe</div>\n```";
    expect(sanitizeAssistantMarkdown(input)).toBe(input);
  });
});
