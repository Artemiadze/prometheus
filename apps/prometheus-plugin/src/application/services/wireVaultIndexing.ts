import type { Unsubscribe, VaultEvent } from "../dto/vault";
import type { Clock } from "../ports/Clock";
import type { SettingsRepository } from "../ports/SettingsRepository";
import type { VaultGateway } from "../ports/VaultGateway";
import type { SyncDocumentChange } from "../use-cases/SyncDocumentChange";
import { DocumentChangeDebouncer } from "./DocumentChangeDebouncer";

export type WireVaultIndexingDeps = {
  readonly vault: VaultGateway;
  readonly sync: SyncDocumentChange;
  readonly settings: SettingsRepository;
  readonly clock: Clock;
  readonly debouncer?: DocumentChangeDebouncer;
};

/**
 * Subscribe vault events → debounced SyncDocumentChange.
 * Call from bootstrap; returns unsubscribe for onunload.
 */
export async function wireVaultIndexing(deps: WireVaultIndexingDeps): Promise<{
  unsubscribe: Unsubscribe;
  debouncer: DocumentChangeDebouncer;
}> {
  const settings = await deps.settings.get();
  const debouncer =
    deps.debouncer ??
    new DocumentChangeDebouncer(deps.sync, deps.clock, {
      debounceMs: settings.indexingDebounceMs,
      maxConcurrent: settings.maxConcurrentSyncs,
    });

  const unsubscribe = deps.vault.subscribe((event: VaultEvent) => {
    debouncer.enqueue(event);
  });

  return { unsubscribe, debouncer };
}
