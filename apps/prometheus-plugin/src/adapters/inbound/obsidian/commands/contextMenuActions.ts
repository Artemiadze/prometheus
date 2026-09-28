import type { TAbstractFile } from "obsidian";

import { NotePath } from "../../../../domain/value-objects/NotePath";

export type ContextMenuTarget =
  | { readonly kind: "file"; readonly path: string; readonly extension: string }
  | { readonly kind: "folder"; readonly path: string }
  | { readonly kind: "other" };

export type ContextMenuActionKind = "askAboutNote" | "searchInFolder" | "reindexFile";

export type ContextMenuActionDescriptor = {
  readonly kind: ContextMenuActionKind;
  readonly title: string;
  readonly icon: string;
  readonly path: NotePath;
};

/**
 * Duck-type TFile / TFolder: the obsidian package is types-only (no runtime classes).
 */
export function classifyAbstractFile(file: TAbstractFile): ContextMenuTarget {
  if ("stat" in file && "extension" in file) {
    return {
      kind: "file",
      path: file.path,
      extension: (file as { extension: string }).extension,
    };
  }
  if ("children" in file) {
    return { kind: "folder", path: file.path };
  }
  return { kind: "other" };
}

export function buildContextMenuActions(
  target: ContextMenuTarget,
): readonly ContextMenuActionDescriptor[] {
  if (target.kind === "file" && target.extension === "md") {
    let path: NotePath;
    try {
      path = NotePath.create(target.path);
    } catch {
      return [];
    }
    return [
      {
        kind: "askAboutNote",
        title: "Ask Prometheus about this note",
        icon: "message-square",
        path,
      },
      {
        kind: "reindexFile",
        title: "Reindex this note in Prometheus",
        icon: "refresh-cw",
        path,
      },
    ];
  }
  if (target.kind === "folder") {
    if (!target.path) {
      return [];
    }
    let path: NotePath;
    try {
      path = NotePath.create(target.path);
    } catch {
      return [];
    }
    return [
      {
        kind: "searchInFolder",
        title: "Search this folder in Prometheus",
        icon: "search",
        path,
      },
    ];
  }
  return [];
}
