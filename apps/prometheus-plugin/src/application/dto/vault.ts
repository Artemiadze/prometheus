import type { NotePath } from "../../domain/value-objects/NotePath";
import type { NoteOpenMode } from "./settings";

export type VaultFileSnapshot = {
  readonly path: NotePath;
  readonly content: string;
  readonly modifiedAt: Date;
  readonly sizeBytes: number;
};

export type VaultEvent =
  | { readonly type: "create"; readonly path: NotePath }
  | { readonly type: "modify"; readonly path: NotePath }
  | { readonly type: "delete"; readonly path: NotePath }
  | { readonly type: "rename"; readonly path: NotePath; readonly previousPath: NotePath };

export type Unsubscribe = () => void;

export type OpenNoteOptions = {
  readonly heading?: string | null;
  readonly mode?: NoteOpenMode;
};
