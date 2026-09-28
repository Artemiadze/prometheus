import { describe, expect, it } from "vitest";

import {
  normalizeIgnoredFolderPath,
  validateIgnoredFolderPath,
} from "../../../../../src/adapters/inbound/obsidian/settings/folderValidation";

describe("folderValidation", () => {
  it("normalizes relative folder paths", () => {
    expect(normalizeIgnoredFolderPath(" Templates ")).toBe("Templates/");
    expect(normalizeIgnoredFolderPath("./Archive")).toBe("Archive/");
    expect(normalizeIgnoredFolderPath("notes/")).toBe("notes/");
  });

  it("rejects empty and traversal paths", () => {
    expect(validateIgnoredFolderPath("", () => true).ok).toBe(false);
    expect(validateIgnoredFolderPath("../outside", () => true).ok).toBe(false);
  });

  it("rejects folders that do not exist", () => {
    const result = validateIgnoredFolderPath("Missing", () => false);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.message).toContain("does not exist");
    }
  });

  it("accepts existing folders", () => {
    const result = validateIgnoredFolderPath("Templates", (path) => path === "Templates");
    expect(result).toEqual({ ok: true, normalized: "Templates/" });
  });
});
