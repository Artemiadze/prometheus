import { describe, expect, it } from "vitest";

import type { TAbstractFile } from "obsidian";

import {
  buildContextMenuActions,
  classifyAbstractFile,
} from "../../../../../src/adapters/inbound/obsidian/commands/contextMenuActions";

function fakeFile(path: string, extension: string): TAbstractFile {
  return {
    path,
    name: path.split("/").pop() ?? path,
    parent: null,
    vault: {} as TAbstractFile["vault"],
    stat: { ctime: 0, mtime: 0, size: 0 },
    extension,
    basename: path.replace(/\.md$/, ""),
  } as unknown as TAbstractFile;
}

function fakeFolder(path: string): TAbstractFile {
  return {
    path,
    name: path.split("/").pop() ?? path,
    parent: null,
    vault: {} as TAbstractFile["vault"],
    children: [],
  } as unknown as TAbstractFile;
}

describe("classifyAbstractFile", () => {
  it("classifies markdown files, folders, and other", () => {
    expect(classifyAbstractFile(fakeFile("a.md", "md"))).toEqual({
      kind: "file",
      path: "a.md",
      extension: "md",
    });
    expect(classifyAbstractFile(fakeFolder("notes"))).toEqual({
      kind: "folder",
      path: "notes",
    });
    expect(
      classifyAbstractFile({
        path: "x",
        name: "x",
        parent: null,
        vault: {} as TAbstractFile["vault"],
      }),
    ).toEqual({ kind: "other" });
  });
});

describe("buildContextMenuActions", () => {
  it("returns ask and reindex for markdown files", () => {
    const actions = buildContextMenuActions({
      kind: "file",
      path: "folder/note.md",
      extension: "md",
    });
    expect(actions.map((a) => a.kind)).toEqual(["askAboutNote", "reindexFile"]);
    expect(actions[0]?.path.value).toBe("folder/note.md");
  });

  it("returns nothing for non-markdown files", () => {
    expect(buildContextMenuActions({ kind: "file", path: "image.png", extension: "png" })).toEqual(
      [],
    );
  });

  it("returns search for folders and nothing for vault root", () => {
    const actions = buildContextMenuActions({ kind: "folder", path: "Projects" });
    expect(actions).toHaveLength(1);
    expect(actions[0]?.kind).toBe("searchInFolder");
    expect(actions[0]?.path.value).toBe("Projects");

    expect(buildContextMenuActions({ kind: "folder", path: "" })).toEqual([]);
  });

  it("returns nothing for other targets", () => {
    expect(buildContextMenuActions({ kind: "other" })).toEqual([]);
  });
});
