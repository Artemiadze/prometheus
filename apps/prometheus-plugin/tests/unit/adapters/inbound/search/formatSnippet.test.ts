import { describe, expect, it } from "vitest";

import { toPlainSnippet } from "../../../../../src/adapters/inbound/obsidian/search/formatSnippet";

describe("toPlainSnippet", () => {
  it("strips markdown and preserves link labels", () => {
    expect(toPlainSnippet("## Title\n**bold** and [text](https://x) plus [[a|alias]]")).toBe(
      "Title bold and text plus alias",
    );
  });

  it("truncates on a word boundary", () => {
    const long = "alpha beta gamma delta epsilon zeta eta theta iota kappa";
    const snippet = toPlainSnippet(long, 20);
    expect(snippet.endsWith("…")).toBe(true);
    expect(snippet.includes("alph")).toBe(true);
    expect(snippet.length).toBeLessThanOrEqual(21);
  });
});
