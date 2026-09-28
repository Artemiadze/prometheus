import type { Menu, Plugin, TAbstractFile } from "obsidian";

import type { NotePath } from "../../../../domain/value-objects/NotePath";
import { buildContextMenuActions, classifyAbstractFile } from "./contextMenuActions";

export type ContextMenuHandlers = {
  readonly askAboutNote: (path: NotePath) => void;
  readonly searchInFolder: (path: NotePath) => void;
  readonly reindexFile: (path: NotePath) => void;
};

export function registerContextMenu(plugin: Plugin, handlers: ContextMenuHandlers): void {
  plugin.registerEvent(
    plugin.app.workspace.on("file-menu", (menu: Menu, file: TAbstractFile) => {
      for (const action of buildContextMenuActions(classifyAbstractFile(file))) {
        menu.addItem((item) => {
          item
            .setTitle(action.title)
            .setIcon(action.icon)
            .onClick(() => {
              handlers[action.kind](action.path);
            });
        });
      }
    }),
  );
}
