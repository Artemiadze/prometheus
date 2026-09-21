import { describe, expect, it } from "vitest";

import { InvalidSearchScopeError } from "../errors";
import { NotePath } from "./NotePath";
import { SearchScope } from "./SearchScope";

describe("SearchScope", () => {
  it("creates an entire-vault scope without extra parameters", () => {
    const scope = SearchScope.entireVault();
    expect(scope.serialize()).toEqual({
      mode: "entire_vault",
      note: null,
      folders: [],
    });
  });

  it("creates a current-note scope", () => {
    const scope = SearchScope.currentNote("notes/a.md");
    expect(scope.serialize()).toEqual({
      mode: "current_note",
      note: "notes/a.md",
      folders: [],
    });
  });

  it("creates a current-folder scope with exactly one folder", () => {
    const scope = SearchScope.currentFolder(NotePath.create("projects"));
    expect(scope.serialize()).toEqual({
      mode: "current_folder",
      note: null,
      folders: ["projects"],
    });
  });

  it("deduplicates selected folders and rejects an empty list", () => {
    const scope = SearchScope.selectedFolders(["a", "b", "a"]);
    expect(scope.serialize()).toEqual({
      mode: "selected_folders",
      note: null,
      folders: ["a", "b"],
    });
    expect(() => SearchScope.selectedFolders([])).toThrow(InvalidSearchScopeError);
  });
});
