import type { NotePath } from "../../domain/value-objects/NotePath";
import type { OpenNoteOptions, Unsubscribe, VaultEvent, VaultFileSnapshot } from "../dto/vault";

/**
 * Outbound port to the Obsidian Vault.
 * Does not expose TFile, TFolder, or App.
 */
export interface VaultGateway {
  readFile(path: NotePath, signal?: AbortSignal): Promise<VaultFileSnapshot>;
  listMarkdownFiles(signal?: AbortSignal): Promise<readonly NotePath[]>;
  getVaultSnapshot(signal?: AbortSignal): Promise<readonly VaultFileSnapshot[]>;
  subscribe(listener: (event: VaultEvent) => void): Unsubscribe;
  openNote(path: NotePath, options?: OpenNoteOptions, signal?: AbortSignal): Promise<void>;
  getActiveNotePath(): NotePath | null;
  getActiveFolderPath(): NotePath | null;
}
