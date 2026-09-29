import { describe, expect, it } from "vitest";

import { sanitizeLogFields } from "../../../src/application/services/sanitizeLogFields";

describe("sanitizeLogFields", () => {
  it("drops blocked keys and long or multiline strings", () => {
    const cleaned = sanitizeLogFields({
      requestId: "abc",
      attempt: 2,
      ok: true,
      sessionToken: "secret-value",
      query: "find my notes",
      note: "Daily note body",
      content: "long note text",
      text: "assistant reply",
      password: "x",
      long: "x".repeat(65),
      multiline: "a\nb",
    });
    expect(cleaned).toEqual({ requestId: "abc", attempt: 2, ok: true });
  });

  it("returns empty object for undefined", () => {
    expect(sanitizeLogFields(undefined)).toEqual({});
  });
});
