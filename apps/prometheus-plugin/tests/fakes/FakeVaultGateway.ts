import type {
  OpenNoteOptions,
  VaultEvent,
  VaultFileSnapshot,
} from "../../src/application/dto/vault";
import type { VaultGateway } from "../../src/application/ports/VaultGateway";
import { NotePath } from "../../src/domain/value-objects/NotePath";

type StoredFile = {
  content: string;
  modifiedAt: Date;
};

export type OpenNoteCall = {
  readonly path: NotePath;
  readonly options: OpenNoteOptions;
};

export class FakeVaultGateway implements VaultGateway {
  private readonly files = new Map<string, StoredFile>();
  private readonly listeners = new Set<(event: VaultEvent) => void>();
  private activeNote: NotePath | null = null;
  private activeFolder: NotePath | null = null;
  readonly openNoteCalls: OpenNoteCall[] = [];

  seed(path: NotePath | string, content: string, modifiedAt: Date = new Date(0)): void {
    const notePath = toPath(path);
    this.files.set(notePath.value, { content, modifiedAt });
  }

  setActiveNote(path: NotePath | string | null): void {
    this.activeNote = path === null ? null : toPath(path);
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
    return { path, content: stored.content, modifiedAt: stored.modifiedAt };
  }

  async listMarkdownFiles(signal?: AbortSignal): Promise<readonly NotePath[]> {
    throwIfAborted(signal);
    return [...this.files.keys()]
      .filter((key) => key.endsWith(".md"))
      .map((key) => NotePath.create(key));
  }

  async getVaultSnapshot(signal?: AbortSignal): Promise<readonly VaultFileSnapshot[]> {
    throwIfAborted(signal);
    return [...this.files.entries()].map(([key, stored]) => ({
      path: NotePath.create(key),
      content: stored.content,
      modifiedAt: stored.modifiedAt,
    }));
  }

  subscribe(listener: (event: VaultEvent) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
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
