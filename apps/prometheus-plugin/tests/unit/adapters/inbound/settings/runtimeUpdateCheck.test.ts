import { describe, expect, it } from "vitest";

import { isUpdateAvailable } from "../../../../../src/adapters/inbound/obsidian/settings/runtimeUpdateCheck";

describe("isUpdateAvailable", () => {
  it("returns false when versions match", () => {
    expect(isUpdateAvailable("0.1.0", "0.1.0")).toBe(false);
  });

  it("returns true when bundled is newer", () => {
    expect(isUpdateAvailable("0.1.0", "0.1.1")).toBe(true);
    expect(isUpdateAvailable("0.1.0", "0.2.0")).toBe(true);
  });

  it("returns false when installed is newer", () => {
    expect(isUpdateAvailable("0.2.0", "0.1.0")).toBe(false);
  });

  it("returns false when installed is null", () => {
    expect(isUpdateAvailable(null, "0.1.0")).toBe(false);
  });
});
