import type { App } from "obsidian";

import { ChatStore } from "../adapters/inbound/obsidian/chat/ChatStore";
import { ObsidianVaultGateway } from "../adapters/outbound/vault";
import type { Notifier } from "../application/ports/Notifier";
import type { RagGateway } from "../application/ports/RagGateway";
import type { SettingsRepository } from "../application/ports/SettingsRepository";
import { AskQuestion } from "../application/use-cases/AskQuestion";
import { OpenSourceNote } from "../application/use-cases/OpenSourceNote";
import type { StartRuntime } from "../application/use-cases/StartRuntime";
import type { SearchScope } from "../domain/value-objects/SearchScope";
import { createEnsureRuntime } from "./ensureRuntime";

export type WireChatDeps = {
  readonly app: App;
  readonly settings: SettingsRepository;
  readonly rag: RagGateway;
  readonly startRuntime: StartRuntime;
  readonly notifier: Notifier;
  readonly vault?: ObsidianVaultGateway;
  readonly resolveScope?: () => Promise<SearchScope>;
  readonly onActivated?: () => void;
};

export type WiredChat = {
  readonly store: ChatStore;
  readonly dispose: () => void;
};

export function wireChat(deps: WireChatDeps): WiredChat {
  const vault = deps.vault ?? new ObsidianVaultGateway(deps.app);
  const askQuestion = new AskQuestion(deps.rag, deps.settings);
  const openSourceNote = new OpenSourceNote(vault, deps.settings, deps.notifier);

  const store = new ChatStore({
    askQuestion,
    openSource: (source) => openSourceNote.execute(source),
    ensureRuntime: createEnsureRuntime(deps.startRuntime, deps.onActivated),
    ...(deps.resolveScope ? { resolveScope: deps.resolveScope } : {}),
  });

  return {
    store,
    dispose: () => {
      store.dispose();
    },
  };
}
