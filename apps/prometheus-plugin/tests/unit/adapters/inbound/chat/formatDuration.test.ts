import { describe, expect, it } from "vitest";

import { formatDuration } from "../../../../../src/adapters/inbound/obsidian/chat/formatDuration";

describe("formatDuration", () => {
  it("formats sub-minute durations", () => {
    expect(formatDuration(0)).toBe("0s");
    expect(formatDuration(14_000)).toBe("14s");
    expect(formatDuration(59_400)).toBe("59s");
  });

  it("formats minutes and seconds", () => {
    expect(formatDuration(72_000)).toBe("1m 12s");
    expect(formatDuration(120_000)).toBe("2m");
  });
});
