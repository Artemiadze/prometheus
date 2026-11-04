import type { VaultEvent } from "../dto/vault";
import type { Notifier } from "../ports/Notifier";
import type { RagGateway } from "../ports/RagGateway";
import type { SettingsRepository } from "../ports/SettingsRepository";
import type { VaultGateway } from "../ports/VaultGateway";
import { computeContentHash } from "../services/contentHash";
import type { DocumentSyncState } from "../services/DocumentSyncState";
import {
  effectiveIgnoredFolders,
  isIgnoredPath,
  requireVaultId,
} from "../services/settingsHelpers";
import { DocumentId } from "../../domain/value-objects/DocumentId";
import type { NotePath } from "../../domain/value-objects/NotePath";

export type SyncDocumentChangeOptions = {
  readonly force?: boolean;
};

export class SyncDocumentChange {
  constructor(
    private readonly vault: VaultGateway,
    private readonly rag: RagGateway,
    private readonly settings: SettingsRepository,
    private readonly syncState: DocumentSyncState,
    private readonly notifier: Notifier,
  ) {}

  async execute(
    event: VaultEvent,
    signal?: AbortSignal,
    options?: SyncDocumentChangeOptions,
  ): Promise<void> {
    await this.executeMany([event], signal, options);
  }

  async executeMany(
    events: readonly VaultEvent[],
    signal?: AbortSignal,
    options?: SyncDocumentChangeOptions,
  ): Promise<void> {
    const settings = await this.settings.get();
    const vaultId = requireVaultId(settings);
    const ignored = effectiveIgnoredFolders(settings);
    const force = options?.force === true;

    for (const event of events) {
      try {
        switch (event.type) {
          case "create":
          case "modify": {
            if (isIgnoredPath(event.path.value, ignored)) {
              break;
            }
            const file = await this.vault.readFile(event.path, signal);
            const contentHash = computeContentHash(file.content);
            const existing = this.syncState.getByPath(event.path);
            if (!force && existing?.contentHash === contentHash) {
              break;
            }
            const documentId = this.syncState.resolveOrCreate(event.path);
            const revision = this.syncState.nextRevision(event.path);
            await this.rag.upsertDocument(
              vaultId,
              documentId,
              {
                path: event.path,
                content: file.content,
                revision,
                modifiedAt: file.modifiedAt,
              },
              signal,
            );
            this.syncState.upsert({
              documentId,
              path: event.path,
              contentHash,
              revision,
            });
            break;
          }
          case "delete": {
            const documentId = this.resolveDeleteId(event.path);
            this.syncState.removeByPath(event.path);
            await this.rag.deleteDocument(vaultId, documentId, signal);
            break;
          }
          case "rename": {
            const previousRecord = this.syncState.removeByPath(event.previousPath);
            const previousId =
              previousRecord?.documentId ?? DocumentId.fromNotePath(event.previousPath);
            await this.rag.deleteDocument(vaultId, previousId, signal);

            if (isIgnoredPath(event.path.value, ignored)) {
              break;
            }

            const documentId = DocumentId.fromNotePath(event.path);
            const file = await this.vault.readFile(event.path, signal);
            const contentHash = computeContentHash(file.content);
            const revision = this.syncState.nextRevision(event.path);
            await this.rag.upsertDocument(
              vaultId,
              documentId,
              {
                path: event.path,
                content: file.content,
                revision,
                modifiedAt: file.modifiedAt,
              },
              signal,
            );
            this.syncState.upsert({
              documentId,
              path: event.path,
              contentHash,
              revision,
            });
            break;
          }
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "unknown error";
        this.notifier.warning(`Failed to sync ${event.path.value}: ${message}`);
      }
    }
  }

  private resolveDeleteId(path: NotePath): DocumentId {
    const record = this.syncState.getByPath(path);
    return record?.documentId ?? DocumentId.fromNotePath(path);
  }
}
