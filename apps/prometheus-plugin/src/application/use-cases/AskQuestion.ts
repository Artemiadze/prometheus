import { ChatMessage } from "../../domain/entities/ChatMessage";
import type { ChatSession } from "../../domain/entities/ChatSession";
import { dedupeSourceReferences } from "../../domain/entities/SourceReference";
import type { SearchScope } from "../../domain/value-objects/SearchScope";
import { isAbortError, QueryTooShortError } from "../../domain/errors";
import type { SourceReference } from "../../domain/entities/SourceReference";
import type { RagGateway } from "../ports/RagGateway";
import type { SettingsRepository } from "../ports/SettingsRepository";
import { requireVaultId } from "../services/settingsHelpers";
import { MIN_QUERY_LENGTH } from "./SearchNotes";

export type AskQuestionOptions = {
  readonly onSessionUpdate?: (session: ChatSession) => void;
};

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
    options?: AskQuestionOptions,
  ): Promise<AskQuestionResult> {
    const trimmed = question.trim();
    if (trimmed.length < MIN_QUERY_LENGTH) {
      return { kind: "validation", error: new QueryTooShortError() };
    }

    const prepared = prepareQuestionTurn(session, trimmed);
    const pending = prepared.pending;
    let next = prepared.next;

    const publish = (sessionSnapshot: ChatSession): void => {
      options?.onSessionUpdate?.(sessionSnapshot);
    };

    try {
      const settings = await this.settings.get();
      const vaultId = requireVaultId(settings);
      let streamedText = "";
      let streamedSources: readonly SourceReference[] = [];
      let insufficientContext = false;
      let done = false;

      await this.rag.chatStream(
        vaultId,
        trimmed,
        scope,
        {
          onToken: (_delta, fullText) => {
            streamedText = fullText;
            next = next.replaceMessage(
              pending.id,
              ChatMessage.assistant(fullText, {
                id: pending.id,
                createdAt: pending.createdAt,
                state: "streaming",
                sources: streamedSources,
                insufficientContext,
              }),
            );
            publish(next);
          },
          onSources: (sources, insufficient) => {
            streamedSources = dedupeSourceReferences(sources);
            insufficientContext = insufficient;
            next = next.replaceMessage(
              pending.id,
              ChatMessage.assistant(streamedText, {
                id: pending.id,
                createdAt: pending.createdAt,
                state: streamedText.length > 0 ? "streaming" : "pending",
                sources: streamedSources,
                insufficientContext,
              }),
            );
            publish(next);
          },
          onDone: () => {
            done = true;
          },
        },
        signal,
      );

      if (!done) {
        throw new Error("Chat stream ended before completion");
      }

      const completed = ChatMessage.assistant(streamedText, {
        id: pending.id,
        createdAt: pending.createdAt,
        state: "complete",
        sources: streamedSources,
        insufficientContext,
      });
      next = next.replaceMessage(pending.id, completed);
      publish(next);
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

function prepareQuestionTurn(
  session: ChatSession,
  trimmed: string,
): { readonly next: ChatSession; readonly pending: ChatMessage } {
  const messages = session.messages;
  const last = messages[messages.length - 1];
  const prev = messages[messages.length - 2];
  if (
    last?.kind === "assistant" &&
    last.state === "pending" &&
    prev?.kind === "user" &&
    prev.text === trimmed
  ) {
    return { next: session, pending: last };
  }
  const pending = ChatMessage.assistant("", { state: "pending" });
  const next = session.appendMessage(ChatMessage.user(trimmed)).appendMessage(pending);
  return { next, pending };
}
