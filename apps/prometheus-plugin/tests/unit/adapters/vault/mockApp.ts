import type { App, EventRef, TAbstractFile, TFile } from "obsidian";

type VaultListener = (...args: unknown[]) => void;

export type MockVaultFile = TFile & { __content: string };

/**
 * Lightweight Obsidian App/Vault/Workspace mock for adapter unit tests.
 * Avoids importing runtime values from the types-only `obsidian` package.
 */
export function createMockApp(
  initial: Array<{ path: string; content: string; mtime?: number }> = [],
): {
  app: App;
  files: Map<string, MockVaultFile>;
  readPaths: string[];
  yieldCount: { value: number };
  openLinkCalls: Array<{ linktext: string; newLeaf: boolean }>;
  openFileCalls: Array<{ path: string; newLeaf: boolean }>;
  setActiveFile: (path: string | null) => void;
  emitVault: (event: "create" | "modify" | "delete", path: string) => void;
  emitRename: (oldPath: string, newPath: string) => void;
  emitActiveLeafChange: () => void;
  addFile: (path: string, content: string, mtime?: number) => MockVaultFile;
  removeFile: (path: string) => void;
} {
  const files = new Map<string, MockVaultFile>();
  const readPaths: string[] = [];
  const yieldCount = { value: 0 };
  const openLinkCalls: Array<{ linktext: string; newLeaf: boolean }> = [];
  const openFileCalls: Array<{ path: string; newLeaf: boolean }> = [];
  const vaultListeners = new Map<string, Set<VaultListener>>();
  const workspaceListeners = new Map<string, Set<VaultListener>>();
  let activePath: string | null = null;

  function addFile(path: string, content: string, mtime = 0): MockVaultFile {
    const file = {
      path,
      name: path.includes("/") ? path.slice(path.lastIndexOf("/") + 1) : path,
      extension: path.includes(".") ? path.slice(path.lastIndexOf(".") + 1) : "",
      basename: "",
      parent: null,
      vault: null,
      stat: { ctime: mtime, mtime, size: Buffer.byteLength(content, "utf8") },
      __content: content,
    } as unknown as MockVaultFile;
    file.basename = file.name.replace(/\.[^.]+$/, "");
    files.set(path, file);
    return file;
  }

  function removeFile(path: string): void {
    files.delete(path);
  }

  for (const entry of initial) {
    addFile(entry.path, entry.content, entry.mtime);
  }

  const refMeta = new WeakMap<
    EventRef,
    { name: string; callback: VaultListener; store: Map<string, Set<VaultListener>> }
  >();

  function on(
    store: Map<string, Set<VaultListener>>,
    name: string,
    callback: VaultListener,
  ): EventRef {
    let set = store.get(name);
    if (!set) {
      set = new Set();
      store.set(name, set);
    }
    set.add(callback);
    const ref: EventRef = { __mock: true };
    refMeta.set(ref, { name, callback, store });
    return ref;
  }

  function offref(_store: Map<string, Set<VaultListener>>, ref: EventRef): void {
    const meta = refMeta.get(ref);
    if (!meta) {
      return;
    }
    meta.store.get(meta.name)?.delete(meta.callback);
    refMeta.delete(ref);
  }

  const app = {
    vault: {
      getMarkdownFiles: () => [...files.values()].filter((f) => f.extension === "md"),
      getAbstractFileByPath: (path: string): TAbstractFile | null => files.get(path) ?? null,
      cachedRead: async (file: TFile) => {
        readPaths.push(file.path);
        const stored = files.get(file.path);
        if (!stored) {
          throw new Error(`missing ${file.path}`);
        }
        if (stored.__content === "__THROW__") {
          throw new Error(`read failed: ${file.path}`);
        }
        return stored.__content;
      },
      read: async (file: TFile) => {
        readPaths.push(file.path);
        return files.get(file.path)?.__content ?? "";
      },
      on: (name: string, callback: VaultListener) => on(vaultListeners, name, callback),
      offref: (ref: EventRef) => {
        offref(vaultListeners, ref);
      },
    },
    workspace: {
      getActiveFile: () => (activePath ? (files.get(activePath) ?? null) : null),
      getLeaf: (newLeaf?: boolean) => ({
        openFile: async (file: TFile) => {
          openFileCalls.push({ path: file.path, newLeaf: Boolean(newLeaf) });
          activePath = file.path;
        },
        view: null,
      }),
      openLinkText: async (linktext: string, _source: string, newLeaf?: boolean) => {
        openLinkCalls.push({ linktext, newLeaf: Boolean(newLeaf) });
        const path = linktext.split("#")[0] ?? linktext;
        activePath = path;
      },
      on: (name: string, callback: VaultListener) => on(workspaceListeners, name, callback),
      offref: (ref: EventRef) => {
        offref(workspaceListeners, ref);
      },
    },
    metadataCache: {
      getFileCache: (_file: TFile) => null,
    },
  } as unknown as App;

  return {
    app,
    files,
    readPaths,
    yieldCount,
    openLinkCalls,
    openFileCalls,
    setActiveFile: (path) => {
      activePath = path;
    },
    emitVault: (event, path) => {
      const file = files.get(path);
      if (!file) {
        return;
      }
      for (const cb of vaultListeners.get(event) ?? []) {
        cb(file);
      }
    },
    emitRename: (oldPath, newPath) => {
      const file = files.get(newPath) ?? files.get(oldPath);
      if (!file) {
        return;
      }
      if (files.has(oldPath) && oldPath !== newPath) {
        const content = files.get(oldPath)!.__content;
        removeFile(oldPath);
        addFile(newPath, content, file.stat.mtime);
      }
      const renamed = files.get(newPath)!;
      for (const cb of vaultListeners.get("rename") ?? []) {
        cb(renamed, oldPath);
      }
    },
    emitActiveLeafChange: () => {
      for (const cb of workspaceListeners.get("active-leaf-change") ?? []) {
        cb(null);
      }
    },
    addFile,
    removeFile,
  };
}
