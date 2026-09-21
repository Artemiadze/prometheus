import type { NotePath } from "../../domain/value-objects/NotePath";

export type VaultFileSnapshot = {
  readonly path: NotePath;
  readonly content: string;
  readonly modifiedAt: Date;
};

export type VaultEvent =
  | { readonly type: "create"; readonly path: NotePath }
  | { readonly type: "modify"; readonly path: NotePath }
  | { readonly type: "delete"; readonly path: NotePath }
  | { readonly type: "rename"; readonly path: NotePath; readonly previousPath: NotePath };

export type Unsubscribe = () => void;
