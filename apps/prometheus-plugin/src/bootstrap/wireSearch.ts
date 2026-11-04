import type { App } from "obsidian";

import { SearchStore } from "../adapters/inbound/obsidian/search/SearchStore";
import { resolveScope } from "../adapters/inbound/obsidian/search/scopeOptions";
import { SystemClock } from "../adapters/outbound/system/SystemClock";
import { ObsidianVaultGateway } from "../adapters/outbound/vault";
import type { Notifier } from "../application/ports/Notifier";
import type { RagGateway } from "../application/ports/RagGateway";
import type { SettingsRepository } from "../application/ports/SettingsRepository";
import { OpenSourceNote } from "../application/use-cases/OpenSourceNote";
import { SearchNotes } from "../application/use-cases/SearchNotes";
import type { StartRuntime } from "../application/use-cases/StartRuntime";
import type { ChatScopeMode } from "../adapters/inbound/obsidian/chat/ChatStore";
import type { SearchScopePreference } from "../application/dto/settings";
import { SearchScope } from "../domain/value-objects/SearchScope";
import { createEnsureRuntime } from "./ensureRuntime";

export type WireSearchDeps = {
  readonly app: App;
  readonly settings: SettingsRepository;
  readonly rag: RagGateway;
  readonly startRuntime: StartRuntime;
  readonly notifier: Notifier;
  readonly onActivated?: () => void;
};

export type WiredSearch = {
  readonly store: SearchStore;
  readonly vault: ObsidianVaultGateway;
  readonly dispose: () => void;
};

export function wireSearch(deps: WireSearchDeps): WiredSearch {
  const vault = new ObsidianVaultGateway(deps.app);
  const searchNotes = new SearchNotes(deps.rag, deps.settings);
  const openSourceNote = new OpenSourceNote(vault, deps.settings, deps.notifier);

  const store = new SearchStore({
    searchNotes,
    ensureRuntime: createEnsureRuntime(deps.startRuntime, deps.onActivated),
    openSource: (source) => openSourceNote.execute(source),
    settings: deps.settings,
    vault,
    clock: new SystemClock(),
  });

  return {
    store,
    vault,
    dispose: () => {
      store.dispose();
    },
  };
}

export function createChatScopeResolver(deps: {
  readonly settings: SettingsRepository;
  readonly vault: ObsidianVaultGateway;
}): (mode: ChatScopeMode) => Promise<SearchScope> {
  return async (mode) => {
    if (mode !== "auto") {
      return resolveScope(
        chatScopeModeToPreference(mode),
        deps.vault.getActiveNotePath(),
        deps.vault.getActiveFolderPath(),
      );
    }
    const settings = await deps.settings.get();
    if (!settings.applySearchScopeToChat) {
      return SearchScope.entireVault();
    }
    return resolveScope(
      settings.searchScopeMode,
      deps.vault.getActiveNotePath(),
      deps.vault.getActiveFolderPath(),
    );
  };
}

function chatScopeModeToPreference(mode: Exclude<ChatScopeMode, "auto">): SearchScopePreference {
  return mode;
}
