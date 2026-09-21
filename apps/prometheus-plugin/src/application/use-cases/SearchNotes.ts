import type { SearchHitDto } from "../dto/rag";
import type { SearchScope } from "../../domain/value-objects/SearchScope";
import { QueryTooShortError, isAbortError } from "../../domain/errors";
import type { RagGateway } from "../ports/RagGateway";
import type { SettingsRepository } from "../ports/SettingsRepository";
import { requireVaultId } from "../services/settingsHelpers";

export const MIN_QUERY_LENGTH = 3;

export type SearchNotesResult =
  | { readonly kind: "ok"; readonly hits: readonly SearchHitDto[] }
  | { readonly kind: "validation"; readonly error: QueryTooShortError }
  | { readonly kind: "aborted" };

export class SearchNotes {
  private inFlight: AbortController | null = null;

  constructor(
    private readonly rag: RagGateway,
    private readonly settings: SettingsRepository,
    private readonly minQueryLength = MIN_QUERY_LENGTH,
  ) {}

  async execute(
    query: string,
    scope: SearchScope,
    limit = 10,
    signal?: AbortSignal,
  ): Promise<SearchNotesResult> {
    const trimmed = query.trim();
    if (trimmed.length < this.minQueryLength) {
      return { kind: "validation", error: new QueryTooShortError() };
    }

    this.inFlight?.abort();
    const local = new AbortController();
    this.inFlight = local;
    const combined = combineSignals(local.signal, signal);

    try {
      const settings = await this.settings.get();
      const vaultId = requireVaultId(settings);
      const hits = await this.rag.search(vaultId, trimmed, scope, limit, combined);
      return { kind: "ok", hits };
    } catch (error) {
      if (isAbortError(error)) {
        return { kind: "aborted" };
      }
      throw error;
    } finally {
      if (this.inFlight === local) {
        this.inFlight = null;
      }
    }
  }
}

function combineSignals(a: AbortSignal, b?: AbortSignal): AbortSignal {
  if (!b) {
    return a;
  }
  const controller = new AbortController();
  const onAbort = (): void => controller.abort();
  if (a.aborted || b.aborted) {
    controller.abort();
    return controller.signal;
  }
  a.addEventListener("abort", onAbort, { once: true });
  b.addEventListener("abort", onAbort, { once: true });
  return controller.signal;
}
