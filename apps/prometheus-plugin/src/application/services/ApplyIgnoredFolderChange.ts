import type { Notifier } from "../ports/Notifier";
import type { RagGateway } from "../ports/RagGateway";
import type { SettingsRepository } from "../ports/SettingsRepository";
import type { DocumentSyncState } from "./DocumentSyncState";
import { effectiveIgnoredFolders, isIgnoredPath, requireVaultId } from "./settingsHelpers";

export type ApplyIgnoredFolderChangeInput = {
  readonly previousIgnoredFolders: readonly string[];
  readonly nextIgnoredFolders: readonly string[];
};

/**
 * When ignored folders expand, delete newly covered documents from RAG + sync state.
 * Settings UI (PLG-65) calls this on save.
 */
export class ApplyIgnoredFolderChange {
  constructor(
    private readonly rag: RagGateway,
    private readonly settings: SettingsRepository,
    private readonly syncState: DocumentSyncState,
    private readonly notifier: Notifier,
  ) {}

  async execute(input: ApplyIgnoredFolderChangeInput, signal?: AbortSignal): Promise<number> {
    const settings = await this.settings.get();
    const vaultId = requireVaultId(settings);

    const previousEffective = effectiveIgnoredFolders({
      ...settings,
      ignoredFolders: input.previousIgnoredFolders,
    });
    const nextEffective = effectiveIgnoredFolders({
      ...settings,
      ignoredFolders: input.nextIgnoredFolders,
    });

    let removed = 0;
    for (const record of [...this.syncState.entries()]) {
      const pathValue = record.path.value;
      const wasIgnored = isIgnoredPath(pathValue, previousEffective);
      const nowIgnored = isIgnoredPath(pathValue, nextEffective);
      if (wasIgnored || !nowIgnored) {
        continue;
      }
      try {
        this.syncState.removeByPath(record.path);
        await this.rag.deleteDocument(vaultId, record.documentId, signal);
        removed += 1;
      } catch {
        this.notifier.warning(`Failed to unindex ${pathValue}. Check Diagnostics.`);
      }
    }
    return removed;
  }
}
