import type { App, WorkspaceLeaf } from "obsidian";

import { CHAT_VIEW_TYPE } from "./ChatView";

export async function activateChatView(app: App): Promise<void> {
  const { workspace } = app;
  let leaf: WorkspaceLeaf | null = workspace.getLeavesOfType(CHAT_VIEW_TYPE)[0] ?? null;
  if (!leaf) {
    leaf = workspace.getRightLeaf(false);
    if (!leaf) {
      return;
    }
    await leaf.setViewState({ type: CHAT_VIEW_TYPE, active: true });
  }
  void workspace.revealLeaf(leaf);
}
