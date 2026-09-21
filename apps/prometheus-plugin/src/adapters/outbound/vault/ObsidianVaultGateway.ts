import type { App, EventRef, TAbstractFile, TFile } from "obsidian";

import type {
  OpenNoteOptions,
  Unsubscribe,
  VaultEvent,
  VaultFileSnapshot,
} from "../../../application/dto/vault";
import type { VaultGateway } from "../../../application/ports/VaultGateway";
import { isIgnoredPath } from "../../../application/services/settingsHelpers";
import { NotePath } from "../../../domain/value-objects/NotePath";
import { openNoteWithHeading } from "./openNoteWithHeading";

export type ObsidianVaultGatewayOptions = {
  readonly batchSize?: number;
  readonly yieldFn?: () => Promise<void>;
  readonly getIgnoredFolders?: () => readonly string[];
};

const DEFAULT_BATCH_SIZE = 40;

/**
 * VaultGateway backed by the Obsidian App/Vault API (no Node fs).
 */
export class ObsidianVaultGateway implements VaultGateway {
  private readonly batchSize: number;
  private readonly yieldFn: () => Promise<void>;
  private readonly getIgnoredFolders: () => readonly string[];

  constructor(
    private readonly app: App,
    options: ObsidianVaultGatewayOptions = {},
  ) {
    this.batchSize = options.batchSize ?? DEFAULT_BATCH_SIZE;
    this.yieldFn = options.yieldFn ?? (() => Promise.resolve());
    this.getIgnoredFolders = options.getIgnoredFolders ?? (() => []);
  }

  async readFile(path: NotePath, signal?: AbortSignal): Promise<VaultFileSnapshot> {
    throwIfAborted(signal);
    const file = this.resolveMarkdownFile(path.value);
    if (!file) {
      throw new Error(`File not found: ${path.value}`);
    }
    const content = await this.app.vault.cachedRead(file);
    throwIfAborted(signal);
    return {
      path,
      content,
      modifiedAt: new Date(file.stat.mtime),
      sizeBytes: file.stat.size,
    };
  }

  async listMarkdownFiles(signal?: AbortSignal): Promise<readonly NotePath[]> {
    throwIfAborted(signal);
    const result: NotePath[] = [];
    for (const file of this.app.vault.getMarkdownFiles()) {
      try {
        result.push(NotePath.create(file.path));
      } catch {
        // Skip invalid paths without aborting the walk.
      }
    }
    return result;
  }

  async getVaultSnapshot(
    signal?: AbortSignal,
    ignoredFolders?: readonly string[],
  ): Promise<readonly VaultFileSnapshot[]> {
    throwIfAborted(signal);
    const ignored = ignoredFolders ?? this.getIgnoredFolders();
    const files = this.app.vault.getMarkdownFiles();
    const result: VaultFileSnapshot[] = [];
    let processed = 0;

    for (const file of files) {
      throwIfAborted(signal);
      if (isIgnoredPath(file.path, ignored)) {
        continue;
      }
      try {
        const path = NotePath.create(file.path);
        const content = await this.app.vault.cachedRead(file);
        result.push({
          path,
          content,
          modifiedAt: new Date(file.stat.mtime),
          sizeBytes: file.stat.size,
        });
      } catch {
        // One bad file must not stop the walk.
      }
      processed += 1;
      if (processed % this.batchSize === 0) {
        await this.yieldFn();
      }
    }
    return result;
  }

  subscribe(listener: (event: VaultEvent) => void): Unsubscribe {
    const refs: EventRef[] = [];

    const emitMarkdown = (type: "create" | "modify" | "delete", file: TAbstractFile): void => {
      const md = asMarkdownFile(file);
      if (!md) {
        return;
      }
      try {
        const path = NotePath.create(md.path);
        listener({ type, path });
      } catch {
        // Ignore invalid paths.
      }
    };

    refs.push(
      this.app.vault.on("create", (file) => {
        emitMarkdown("create", file);
      }),
    );
    refs.push(
      this.app.vault.on("modify", (file) => {
        emitMarkdown("modify", file);
      }),
    );
    refs.push(
      this.app.vault.on("delete", (file) => {
        emitMarkdown("delete", file);
      }),
    );
    refs.push(
      this.app.vault.on("rename", (file, oldPath) => {
        const md = asMarkdownFile(file);
        if (!md) {
          return;
        }
        try {
          listener({
            type: "rename",
            path: NotePath.create(md.path),
            previousPath: NotePath.create(oldPath),
          });
        } catch {
          // Ignore invalid paths.
        }
      }),
    );

    return () => {
      for (const ref of refs) {
        this.app.vault.offref(ref);
      }
    };
  }

  subscribeActiveFile(listener: (path: NotePath | null) => void): Unsubscribe {
    const notify = (): void => {
      listener(this.getActiveNotePath());
    };
    const ref = this.app.workspace.on("active-leaf-change", () => {
      notify();
    });
    return () => {
      this.app.workspace.offref(ref);
    };
  }

  async openNote(
    path: NotePath,
    options: OpenNoteOptions = {},
    signal?: AbortSignal,
  ): Promise<void> {
    throwIfAborted(signal);
    await openNoteWithHeading(this.app, path, options);
  }

  getActiveNotePath(): NotePath | null {
    const file = this.app.workspace.getActiveFile();
    if (!file || file.extension !== "md") {
      return null;
    }
    try {
      return NotePath.create(file.path);
    } catch {
      return null;
    }
  }

  getActiveFolderPath(): NotePath | null {
    const note = this.getActiveNotePath();
    return note?.parent ?? null;
  }

  private resolveMarkdownFile(pathValue: string): TFile | null {
    const abstract = this.app.vault.getAbstractFileByPath(pathValue);
    return asMarkdownFile(abstract);
  }
}

function asMarkdownFile(file: TAbstractFile | null): TFile | null {
  // Duck-type TFile: obsidian package is types-only (no runtime TFile for instanceof).
  if (!file || !("stat" in file) || !("extension" in file)) {
    return null;
  }
  const tfile = file as TFile;
  if (tfile.extension !== "md") {
    return null;
  }
  return tfile;
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw new DOMException("The operation was aborted", "AbortError");
  }
}
