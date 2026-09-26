import type { App } from "obsidian";

import { ChatStore, type ChatRuntimeReadiness } from "../adapters/inbound/obsidian/chat/ChatStore";
import { ObsidianVaultGateway } from "../adapters/outbound/vault";
import type { RagGateway } from "../application/ports/RagGateway";
import type { Notifier } from "../application/ports/Notifier";
import type { SettingsRepository } from "../application/ports/SettingsRepository";
import { AskQuestion } from "../application/use-cases/AskQuestion";
import { OpenSourceNote } from "../application/use-cases/OpenSourceNote";
import type { StartRuntime } from "../application/use-cases/StartRuntime";

export type WireChatDeps = {
  readonly app: App;
  readonly settings: SettingsRepository;
  readonly rag: RagGateway;
  readonly startRuntime: StartRuntime;
  readonly notifier: Notifier;
};

export type WiredChat = {
  readonly store: ChatStore;
  readonly dispose: () => void;
};

export function wireChat(deps: WireChatDeps): WiredChat {
  const vault = new ObsidianVaultGateway(deps.app);
  const askQuestion = new AskQuestion(deps.rag, deps.settings);
  const openSourceNote = new OpenSourceNote(vault, deps.settings, deps.notifier);

  const store = new ChatStore({
    askQuestion,
    openSource: (source) => openSourceNote.execute(source),
    ensureRuntime: async (signal): Promise<ChatRuntimeReadiness> => {
      const result = await deps.startRuntime.execute(signal);
      switch (result.kind) {
        case "ready":
          return { ok: true };
        case "missing":
          return {
            ok: false,
            message: "Prometheus runtime is not installed. Install it from the status panel.",
          };
        case "incompatible":
          return {
            ok: false,
            message: "Prometheus runtime version is incompatible. Update the sidecar.",
          };
        default: {
          const _exhaustive: never = result;
          return _exhaustive;
        }
      }
    },
  });

  return {
    store,
    dispose: () => {
      store.dispose();
    },
  };
}
