import { describe, expect, it } from "vitest";

import {
  computeContentHash,
  normalizeContent,
} from "../../../src/application/services/contentHash";

describe("contentHash", () => {
  it("matches runtime normalize + sha256 vectors", () => {
    expect(normalizeContent("\ufeffhello\r\nworld  \r")).toBe("hello\nworld\n");
    expect(computeContentHash("hello\n")).toBe(
      "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03",
    );
    expect(computeContentHash("hello\r\n")).toBe(computeContentHash("hello\n"));
  });
});
