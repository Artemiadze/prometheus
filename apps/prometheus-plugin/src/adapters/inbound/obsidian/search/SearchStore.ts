import type { SearchScopePreference } from "../../../../application/dto/settings";
import type { SearchHitDto } from "../../../../application/dto/rag";
import type { Clock } from "../../../../application/ports/Clock";
import type { SettingsRepository } from "../../../../application/ports/SettingsRepository";
import type { VaultGateway } from "../../../../application/ports/VaultGateway";
import type { SearchNotes } from "../../../../application/use-cases/SearchNotes";
import { MIN_QUERY_LENGTH } from "../../../../application/use-cases/SearchNotes";
import { SourceReference } from "../../../../domain/entities/SourceReference";
import type { NotePath } from "../../../../domain/value-objects/NotePath";
import { createScopeOptionsState, resolveScope, type ScopeOptionsState } from "./scopeOptions";

export type SearchStatus = "idle" | "tooShort" | "searching" | "results" | "empty" | "error";

export type SearchRuntimeReadiness =
  { readonly ok: true } | { readonly ok: false; readonly message: string };

export type SearchViewState = {
  readonly query: string;
  readonly status: SearchStatus;
  readonly hits: readonly SearchHitDto[];
  readonly scope: ScopeOptionsState;
  readonly errorMessage: string | null;
};

export type SearchStoreDeps = {
  readonly searchNotes: Pick<SearchNotes, "execute">;
  readonly ensureRuntime: (signal: AbortSignal) => Promise<SearchRuntimeReadiness>;
  readonly openSource: (source: SourceReference) => Promise<void>;
  readonly settings: SettingsRepository;
  readonly vault: Pick<
    VaultGateway,
    "getActiveNotePath" | "getActiveFolderPath" | "subscribeActiveFile"
  >;
  readonly clock: Clock;
  readonly debounceMs?: number;
  readonly limit?: number;
};

type Listener = (state: SearchViewState) => void;

export class SearchStore {
  private query = "";
  private status: SearchStatus = "idle";
  private hits: readonly SearchHitDto[] = [];
  private errorMessage: string | null = null;
  private scopeMode: SearchScopePreference = "entire_vault";
  private scope: ScopeOptionsState;
  private pinnedFolder: NotePath | null = null;
  private readonly listeners = new Set<Listener>();
  private debounceController: AbortController | null = null;
  private searchController: AbortController | null = null;
  private requestSeq = 0;
  private disposed = false;
  private unsubscribeActive: (() => void) | null = null;
  private readonly debounceMs: number;
  private readonly limit: number;
  private ready: Promise<void>;

  constructor(private readonly deps: SearchStoreDeps) {
    this.debounceMs = deps.debounceMs ?? 300;
    this.limit = deps.limit ?? 10;
    this.scope = createScopeOptionsState(
      "entire_vault",
      deps.vault.getActiveNotePath(),
      deps.vault.getActiveFolderPath(),
    );
    this.ready = this.bootstrap();
  }

  getState(): SearchViewState {
    return {
      query: this.query,
      status: this.status,
      hits: this.hits,
      scope: this.scope,
      errorMessage: this.errorMessage,
    };
  }

  subscribe(listener: Listener): () => void {
    if (this.disposed) {
      return () => undefined;
    }
    this.listeners.add(listener);
    listener(this.getState());
    return () => {
      this.listeners.delete(listener);
    };
  }

  async setQuery(text: string): Promise<void> {
    await this.ready;
    if (this.disposed) {
      return;
    }
    this.query = text;
    this.notify();

    this.debounceController?.abort();
    this.searchController?.abort();
    this.debounceController = new AbortController();
    const debounceSignal = this.debounceController.signal;
    const seq = ++this.requestSeq;

    const trimmed = text.trim();
    if (trimmed.length === 0) {
      this.applyStatus(seq, "idle", [], null);
      return;
    }
    if (trimmed.length < MIN_QUERY_LENGTH) {
      this.applyStatus(seq, "tooShort", [], null);
      return;
    }

    try {
      await this.deps.clock.sleep(this.debounceMs, debounceSignal);
    } catch {
      return;
    }
    if (seq !== this.requestSeq || this.disposed) {
      return;
    }
    await this.runSearch(seq, trimmed);
  }

  async setScopeMode(mode: SearchScopePreference): Promise<void> {
    await this.ready;
    if (this.disposed) {
      return;
    }
    this.pinnedFolder = null;
    this.refreshScopeOptions();
    const option = this.scope.options.find((item) => item.mode === mode);
    if (!option?.enabled) {
      this.notify();
      return;
    }
    this.scopeMode = mode;
    this.refreshScopeOptions();
    const settings = await this.deps.settings.get();
    await this.deps.settings.save({ ...settings, searchScopeMode: mode });
    if (this.query.trim().length >= MIN_QUERY_LENGTH) {
      this.searchController?.abort();
      const seq = ++this.requestSeq;
      await this.runSearch(seq, this.query.trim());
    } else {
      this.notify();
    }
  }

  async focusFolder(path: NotePath): Promise<void> {
    await this.ready;
    if (this.disposed) {
      return;
    }
    this.pinnedFolder = path;
    this.scopeMode = "current_folder";
    this.refreshScopeOptions();
    this.notify();
    if (this.query.trim().length >= MIN_QUERY_LENGTH) {
      this.searchController?.abort();
      const seq = ++this.requestSeq;
      await this.runSearch(seq, this.query.trim());
    }
  }

  async openHit(hit: SearchHitDto): Promise<void> {
    await this.deps.openSource(SourceReference.create(hit.path, hit.heading));
  }

  dispose(): void {
    if (this.disposed) {
      return;
    }
    this.disposed = true;
    this.debounceController?.abort();
    this.searchController?.abort();
    this.unsubscribeActive?.();
    this.unsubscribeActive = null;
    this.listeners.clear();
  }

  private async bootstrap(): Promise<void> {
    const settings = await this.deps.settings.get();
    this.scopeMode = settings.searchScopeMode;
    this.refreshScopeOptions();
    this.unsubscribeActive = this.deps.vault.subscribeActiveFile(() => {
      if (this.disposed) {
        return;
      }
      this.refreshScopeOptions();
      this.notify();
      if (this.query.trim().length >= MIN_QUERY_LENGTH) {
        const seq = ++this.requestSeq;
        void this.runSearch(seq, this.query.trim());
      }
    });
    this.notify();
  }

  private refreshScopeOptions(): void {
    this.scope = createScopeOptionsState(
      this.scopeMode,
      this.deps.vault.getActiveNotePath(),
      this.deps.vault.getActiveFolderPath(),
      this.pinnedFolder,
    );
  }

  private async runSearch(seq: number, trimmed: string): Promise<void> {
    this.searchController?.abort();
    const controller = new AbortController();
    this.searchController = controller;
    this.applyStatus(seq, "searching", [], null);

    const readiness = await this.deps.ensureRuntime(controller.signal);
    if (seq !== this.requestSeq || this.disposed) {
      return;
    }
    if (!readiness.ok) {
      if (controller.signal.aborted) {
        return;
      }
      this.applyStatus(seq, "error", [], readiness.message);
      return;
    }

    const scope = resolveScope(
      this.scopeMode,
      this.deps.vault.getActiveNotePath(),
      this.deps.vault.getActiveFolderPath(),
      this.pinnedFolder,
    );

    try {
      const result = await this.deps.searchNotes.execute(
        trimmed,
        scope,
        this.limit,
        controller.signal,
      );
      if (seq !== this.requestSeq || this.disposed) {
        return;
      }
      if (result.kind === "aborted") {
        return;
      }
      if (result.kind === "validation") {
        this.applyStatus(seq, "tooShort", [], null);
        return;
      }
      if (result.hits.length === 0) {
        this.applyStatus(seq, "empty", [], null);
        return;
      }
      this.applyStatus(seq, "results", result.hits, null);
    } catch (error) {
      if (seq !== this.requestSeq || this.disposed || controller.signal.aborted) {
        return;
      }
      this.applyStatus(seq, "error", [], "Unable to search notes.");
      void error;
    }
  }

  private applyStatus(
    seq: number,
    status: SearchStatus,
    hits: readonly SearchHitDto[],
    errorMessage: string | null,
  ): void {
    if (seq !== this.requestSeq || this.disposed) {
      return;
    }
    this.status = status;
    this.hits = hits;
    this.errorMessage = errorMessage;
    this.notify();
  }

  private notify(): void {
    const snapshot = this.getState();
    for (const listener of this.listeners) {
      listener(snapshot);
    }
  }
}
