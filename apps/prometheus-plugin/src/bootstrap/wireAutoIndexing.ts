import type { Unsubscribe, VaultEvent } from "../application/dto/vault";
import type { Clock } from "../application/ports/Clock";
import type { Notifier } from "../application/ports/Notifier";
import type { RagGateway } from "../application/ports/RagGateway";
import type { SettingsRepository } from "../application/ports/SettingsRepository";
import type { VaultGateway } from "../application/ports/VaultGateway";
import { DocumentChangeDebouncer } from "../application/services/DocumentChangeDebouncer";
import type { DocumentSyncState } from "../application/services/DocumentSyncState";
import { SyncDocumentChange } from "../application/use-cases/SyncDocumentChange";
import { SystemClock } from "../adapters/outbound/system/SystemClock";

export type WireAutoIndexingDeps = {
  readonly vault: VaultGateway;
  readonly rag: RagGateway;
  readonly settings: SettingsRepository;
  readonly syncState: DocumentSyncState;
  readonly notifier: Notifier;
  readonly clock?: Clock;
};

export type WiredAutoIndexing = {
  readonly setEnabled: (enabled: boolean) => void;
  readonly isEnabled: () => boolean;
  readonly applySettingsEnabled: () => Promise<void>;
  readonly updateDebounce: (options: { debounceMs?: number; maxConcurrent?: number }) => void;
  readonly dispose: () => void;
};

/**
 * Subscribes vault events → SyncDocumentChange when autoIndexing is enabled.
 * Attachment is deferred until applySettingsEnabled() (PLG-78).
 */
export function wireAutoIndexing(deps: WireAutoIndexingDeps): WiredAutoIndexing {
  const clock = deps.clock ?? new SystemClock();
  const sync = new SyncDocumentChange(
    deps.vault,
    deps.rag,
    deps.settings,
    deps.syncState,
    deps.notifier,
  );
  let debounceMs = 5000;
  let maxConcurrent = 2;
  const debouncer = new DocumentChangeDebouncer(sync, clock, { debounceMs, maxConcurrent });
  let unsubscribe: Unsubscribe | null = null;
  let enabled = false;
  let settingsApplied = false;

  const attach = (): void => {
    if (unsubscribe) {
      return;
    }
    unsubscribe = deps.vault.subscribe((event: VaultEvent) => {
      if (!enabled) {
        return;
      }
      debouncer.enqueue(event);
    });
  };

  const detach = (): void => {
    unsubscribe?.();
    unsubscribe = null;
  };

  const setEnabled = (next: boolean): void => {
    enabled = next;
    if (next) {
      attach();
    } else {
      detach();
    }
  };

  const applySettingsEnabled = async (): Promise<void> => {
    const settings = await deps.settings.get();
    debounceMs = settings.indexingDebounceMs;
    maxConcurrent = settings.maxConcurrentSyncs;
    debouncer.configure({ debounceMs, maxConcurrent });
    settingsApplied = true;
    setEnabled(settings.autoIndexing);
  };

  return {
    setEnabled: (next) => {
      // Before activation, remember preference without attaching the vault watcher.
      if (!settingsApplied && next) {
        enabled = true;
        return;
      }
      setEnabled(next);
    },
    isEnabled: () => enabled,
    applySettingsEnabled,
    updateDebounce: (options) => {
      if (options.debounceMs !== undefined) {
        debounceMs = options.debounceMs;
      }
      if (options.maxConcurrent !== undefined) {
        maxConcurrent = options.maxConcurrent;
      }
      debouncer.configure({ debounceMs, maxConcurrent });
    },
    dispose: () => {
      detach();
      enabled = false;
      settingsApplied = false;
    },
  };
}
