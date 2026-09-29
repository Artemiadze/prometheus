import { ChatMessage } from "../../domain/entities/ChatMessage";
import type { ChatSession } from "../../domain/entities/ChatSession";
import { dedupeSourceReferences } from "../../domain/entities/SourceReference";
import type { SearchScope } from "../../domain/value-objects/SearchScope";
import { isAbortError, QueryTooShortError } from "../../domain/errors";
import type { RagGateway } from "../ports/RagGateway";
import type { SettingsRepository } from "../ports/SettingsRepository";
import { requireVaultId } from "../services/settingsHelpers";
import { MIN_QUERY_LENGTH } from "./SearchNotes";

export type AskQuestionResult =
  | { readonly kind: "ok"; readonly session: ChatSession }
  | { readonly kind: "validation"; readonly error: QueryTooShortError }
  | { readonly kind: "aborted"; readonly session: ChatSession }
  | { readonly kind: "error"; readonly session: ChatSession; readonly cause: unknown };

export class AskQuestion {
  constructor(
    private readonly rag: RagGateway,
    private readonly settings: SettingsRepository,
  ) {}

  async execute(
    session: ChatSession,
    question: string,
    scope: SearchScope,
    signal?: AbortSignal,
  ): Promise<AskQuestionResult> {
    const trimmed = question.trim();
    if (trimmed.length < MIN_QUERY_LENGTH) {
      return { kind: "validation", error: new QueryTooShortError() };
    }

    const user = ChatMessage.user(trimmed);
    const pending = ChatMessage.assistant("", { state: "pending" });
    let next = session.appendMessage(user).appendMessage(pending);

    try {
      const settings = await this.settings.get();
      const vaultId = requireVaultId(settings);
      const answer = await this.rag.chat(vaultId, trimmed, scope, signal);
      const completed = ChatMessage.assistant(answer.answer, {
        id: pending.id,
        createdAt: pending.createdAt,
        state: "complete",
        sources: dedupeSourceReferences(answer.sources),
        insufficientContext: answer.insufficientContext,
      });
      next = next.replaceMessage(pending.id, completed);
      return { kind: "ok", session: next };
    } catch (error) {
      if (isAbortError(error)) {
        next = next.replaceMessage(
          pending.id,
          ChatMessage.assistant("", {
            id: pending.id,
            createdAt: pending.createdAt,
            state: "cancelled",
            sources: [],
            insufficientContext: false,
          }),
        );
        return { kind: "aborted", session: next };
      }
      next = next.replaceMessage(
        pending.id,
        ChatMessage.assistant("Unable to answer the question.", {
          id: pending.id,
          createdAt: pending.createdAt,
          state: "error",
          sources: [],
          insufficientContext: false,
        }),
      );
      return { kind: "error", session: next, cause: error };
    }
  }
}
