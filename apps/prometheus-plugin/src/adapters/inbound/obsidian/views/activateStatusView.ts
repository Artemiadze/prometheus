import type { App, WorkspaceLeaf } from "obsidian";

import { STATUS_VIEW_TYPE } from "./StatusView";

export async function activateStatusView(app: App): Promise<void> {
  const { workspace } = app;
  let leaf: WorkspaceLeaf | null = workspace.getLeavesOfType(STATUS_VIEW_TYPE)[0] ?? null;
  if (!leaf) {
    leaf = workspace.getRightLeaf(false);
    if (!leaf) {
      return;
    }
    await leaf.setViewState({ type: STATUS_VIEW_TYPE, active: true });
  }
  void workspace.revealLeaf(leaf);
}
