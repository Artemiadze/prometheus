import { describe, expect, it } from "vitest";

import {
  buildScopeOptions,
  resolveScope,
} from "../../../../../src/adapters/inbound/obsidian/search/scopeOptions";
import { NotePath } from "../../../../../src/domain/value-objects/NotePath";

describe("scopeOptions", () => {
  it("disables note and folder modes without an active note", () => {
    const options = buildScopeOptions(null, null);
    expect(options.find((o) => o.mode === "entire_vault")?.enabled).toBe(true);
    expect(options.find((o) => o.mode === "current_note")?.enabled).toBe(false);
    expect(options.find((o) => o.mode === "current_folder")?.enabled).toBe(false);
  });

  it("disables current folder for vault-root notes", () => {
    const note = NotePath.create("root.md");
    const options = buildScopeOptions(note, null);
    expect(options.find((o) => o.mode === "current_note")?.enabled).toBe(true);
    expect(options.find((o) => o.mode === "current_folder")?.enabled).toBe(false);
    expect(options.find((o) => o.mode === "current_folder")?.reason).toContain("vault root");
  });

  it("falls back to entire vault when mode is unavailable", () => {
    const scope = resolveScope("current_note", null, null);
    expect(scope.mode).toBe("entire_vault");
  });

  it("builds current folder scope when available", () => {
    const note = NotePath.create("folder/note.md");
    const folder = NotePath.create("folder");
    const scope = resolveScope("current_folder", note, folder);
    expect(scope.mode).toBe("current_folder");
    expect(scope.folders[0]?.value).toBe("folder");
  });
});
