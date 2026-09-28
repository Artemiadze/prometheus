import type { App, WorkspaceLeaf } from "obsidian";

import { SEARCH_VIEW_TYPE } from "./SearchView";

export async function activateSearchView(app: App): Promise<void> {
  const { workspace } = app;
  let leaf: WorkspaceLeaf | null = workspace.getLeavesOfType(SEARCH_VIEW_TYPE)[0] ?? null;
  if (!leaf) {
    leaf = workspace.getRightLeaf(false);
    if (!leaf) {
      return;
    }
    await leaf.setViewState({ type: SEARCH_VIEW_TYPE, active: true });
  }
  void workspace.revealLeaf(leaf);
}
