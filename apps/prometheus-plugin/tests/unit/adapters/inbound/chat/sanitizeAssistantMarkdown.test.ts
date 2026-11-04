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

  it("turns single newlines into markdown hard breaks outside code", () => {
    expect(sanitizeAssistantMarkdown("line one\nline two")).toBe("line one  \nline two");
  });

  it("keeps blank lines as paragraph breaks", () => {
    expect(sanitizeAssistantMarkdown("para one\n\npara two")).toBe("para one\n\npara two");
  });

  it("does not alter newlines inside fenced code", () => {
    const input = "intro\n```js\nconst a = 1;\nconst b = 2;\n```\nout";
    expect(sanitizeAssistantMarkdown(input)).toBe(
      "intro  \n```js\nconst a = 1;\nconst b = 2;\n```\nout",
    );
  });
});
