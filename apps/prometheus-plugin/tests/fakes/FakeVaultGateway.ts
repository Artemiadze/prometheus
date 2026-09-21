import type {
  OpenNoteOptions,
  VaultEvent,
  VaultFileSnapshot,
} from "../../src/application/dto/vault";
import type { VaultGateway } from "../../src/application/ports/VaultGateway";
import { isIgnoredPath } from "../../src/application/services/settingsHelpers";
import { NotePath } from "../../src/domain/value-objects/NotePath";

type StoredFile = {
  content: string;
  modifiedAt: Date;
  sizeBytes: number;
};

export type OpenNoteCall = {
  readonly path: NotePath;
  readonly options: OpenNoteOptions;
};

export class FakeVaultGateway implements VaultGateway {
  private readonly files = new Map<string, StoredFile>();
  private readonly listeners = new Set<(event: VaultEvent) => void>();
  private readonly activeListeners = new Set<(path: NotePath | null) => void>();
  private activeNote: NotePath | null = null;
  private activeFolder: NotePath | null = null;
  readonly openNoteCalls: OpenNoteCall[] = [];
  snapshotYields = 0;

  seed(path: NotePath | string, content: string, modifiedAt: Date = new Date(0)): void {
    const notePath = toPath(path);
    this.files.set(notePath.value, {
      content,
      modifiedAt,
      sizeBytes: Buffer.byteLength(content, "utf8"),
    });
  }

  setActiveNote(path: NotePath | string | null): void {
    this.activeNote = path === null ? null : toPath(path);
    for (const listener of this.activeListeners) {
      listener(this.activeNote);
    }
  }

  setActiveFolder(path: NotePath | string | null): void {
    this.activeFolder = path === null ? null : toPath(path);
  }

  emit(event: VaultEvent): void {
    for (const listener of this.listeners) {
      listener(event);
    }
  }

  async readFile(path: NotePath, signal?: AbortSignal): Promise<VaultFileSnapshot> {
    throwIfAborted(signal);
    const stored = this.files.get(path.value);
    if (!stored) {
      throw new Error(`File not found: ${path.value}`);
    }
    return {
      path,
      content: stored.content,
      modifiedAt: stored.modifiedAt,
      sizeBytes: stored.sizeBytes,
    };
  }

  async listMarkdownFiles(signal?: AbortSignal): Promise<readonly NotePath[]> {
    throwIfAborted(signal);
    return [...this.files.keys()]
      .filter((key) => key.endsWith(".md"))
      .map((key) => NotePath.create(key));
  }

  async getVaultSnapshot(
    signal?: AbortSignal,
    ignoredFolders: readonly string[] = [],
  ): Promise<readonly VaultFileSnapshot[]> {
    throwIfAborted(signal);
    const result: VaultFileSnapshot[] = [];
    for (const [key, stored] of this.files.entries()) {
      if (!key.endsWith(".md") || isIgnoredPath(key, ignoredFolders)) {
        continue;
      }
      result.push({
        path: NotePath.create(key),
        content: stored.content,
        modifiedAt: stored.modifiedAt,
        sizeBytes: stored.sizeBytes,
      });
      this.snapshotYields += 1;
      await Promise.resolve();
    }
    return result;
  }

  subscribe(listener: (event: VaultEvent) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  subscribeActiveFile(listener: (path: NotePath | null) => void): () => void {
    this.activeListeners.add(listener);
    return () => {
      this.activeListeners.delete(listener);
    };
  }

  async openNote(
    path: NotePath,
    options: OpenNoteOptions = {},
    signal?: AbortSignal,
  ): Promise<void> {
    throwIfAborted(signal);
    this.openNoteCalls.push({ path, options });
    this.activeNote = path;
  }

  getActiveNotePath(): NotePath | null {
    return this.activeNote;
  }

  getActiveFolderPath(): NotePath | null {
    return this.activeFolder;
  }
}

function toPath(path: NotePath | string): NotePath {
  return path instanceof NotePath ? path : NotePath.create(path);
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw new DOMException("The operation was aborted", "AbortError");
  }
}
