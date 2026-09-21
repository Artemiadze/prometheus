import type { App, Editor, TAbstractFile, TFile } from "obsidian";

import type { OpenNoteOptions } from "../../../application/dto/vault";
import type { NotePath } from "../../../domain/value-objects/NotePath";

/**
 * Open a vault note, optionally navigating to a heading.
 * Prefers Obsidian `#heading` link navigation; falls back to editor scroll via metadataCache.
 */
export async function openNoteWithHeading(
  app: App,
  path: NotePath,
  options: OpenNoteOptions = {},
): Promise<void> {
  const abstract = app.vault.getAbstractFileByPath(path.value);
  if (!isMarkdownFile(abstract)) {
    throw new Error(`File not found: ${path.value}`);
  }
  const file = abstract;
  const heading = options.heading?.trim() || null;
  const mode = options.mode ?? "reuse_active";

  const active = app.workspace.getActiveFile();
  const alreadyActive = active?.path === file.path;
  const openNewLeaf = mode === "open_new_pane" && !alreadyActive;

  if (heading) {
    const linktext = `${path.value}#${heading}`;
    try {
      await app.workspace.openLinkText(linktext, "", openNewLeaf);
    } catch {
      const leaf = app.workspace.getLeaf(openNewLeaf);
      await leaf.openFile(file);
      scrollEditorToHeading(app, file, heading);
    }
    return;
  }

  const leaf = app.workspace.getLeaf(openNewLeaf);
  await leaf.openFile(file);
}

function isMarkdownFile(file: TAbstractFile | null): file is TFile {
  return Boolean(file && "stat" in file && (file as TFile).extension === "md");
}

function scrollEditorToHeading(app: App, file: TFile, heading: string): void {
  const cache = app.metadataCache.getFileCache(file);
  const match = cache?.headings?.find((entry) => entry.heading === heading);
  if (!match) {
    return;
  }
  const leaf = app.workspace.getLeaf(false);
  const view = leaf.view as { editor?: Editor; file?: TFile } | null;
  if (!view?.editor || view.file?.path !== file.path) {
    return;
  }
  const line = match.position.start.line;
  view.editor.setCursor({ line, ch: 0 });
  view.editor.scrollIntoView({ from: { line, ch: 0 }, to: { line, ch: 0 } }, true);
}
