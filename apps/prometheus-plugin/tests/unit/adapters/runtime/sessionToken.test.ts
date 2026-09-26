import { describe, expect, it } from "vitest";

import { generateSessionToken } from "../../../../src/adapters/outbound/runtime/sessionToken";

describe("sessionToken", () => {
  it("generates unique tokens", () => {
    const first = generateSessionToken();
    const second = generateSessionToken();
    expect(first).not.toBe(second);
    expect(first.length).toBeGreaterThan(20);
  });
});
