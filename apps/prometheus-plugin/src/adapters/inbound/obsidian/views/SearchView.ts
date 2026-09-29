import { ItemView, type WorkspaceLeaf } from "obsidian";

import type { SearchHitDto } from "../../../../application/dto/rag";
import { toPlainSnippet } from "../search/formatSnippet";
import type { SearchStore, SearchViewState } from "../search/SearchStore";

export const SEARCH_VIEW_TYPE = "prometheus-search";

export type SearchViewOptions = {
  readonly store: SearchStore;
  readonly onActivate?: () => void;
};

const STATUS_COPY: Record<Exclude<SearchViewState["status"], "results" | "error">, string> = {
  idle: "Type a query to search your notes.",
  tooShort: "Type at least 3 characters.",
  searching: "Searching…",
  empty: "No matching notes found. Try another query or a wider scope.",
};

export class SearchView extends ItemView {
  private readonly store: SearchStore;
  private readonly onActivate: (() => void) | null;
  private unsubscribe: (() => void) | null = null;
  private scopeEl: HTMLElement | null = null;
  private inputEl: HTMLInputElement | null = null;
  private resultsEl: HTMLElement | null = null;
  private statusEl: HTMLElement | null = null;

  constructor(leaf: WorkspaceLeaf, options: SearchViewOptions) {
    super(leaf);
    this.store = options.store;
    this.onActivate = options.onActivate ?? null;
  }

  override getViewType(): string {
    return SEARCH_VIEW_TYPE;
  }

  override getDisplayText(): string {
    return "Prometheus Search";
  }

  override getIcon(): string {
    return "search";
  }

  override async onOpen(): Promise<void> {
    this.onActivate?.();
    const container = this.containerEl.children[1] as HTMLElement;
    container.empty();
    container.addClass("prometheus-search-view");

    container.createEl("h2", { text: "Semantic search", cls: "prometheus-search-view__title" });

    this.scopeEl = container.createDiv({ cls: "prometheus-search-view__scope" });

    const inputRow = container.createDiv({ cls: "prometheus-search-view__input" });
    this.inputEl = inputRow.createEl("input", {
      type: "search",
      attr: { placeholder: "Search your notes…", spellcheck: "false" },
    });
    this.inputEl.addEventListener("input", () => {
      void this.store.setQuery(this.inputEl?.value ?? "");
    });

    this.statusEl = container.createDiv({ cls: "prometheus-search-view__status" });
    this.resultsEl = container.createDiv({ cls: "prometheus-search-view__results" });

    this.unsubscribe = this.store.subscribe((state) => {
      this.render(state);
    });
  }

  override async onClose(): Promise<void> {
    this.unsubscribe?.();
    this.unsubscribe = null;
    this.containerEl.empty();
  }

  private render(state: SearchViewState): void {
    this.renderScope(state);
    this.renderStatus(state);
    this.renderResults(state);
    if (this.inputEl && this.inputEl.value !== state.query) {
      this.inputEl.value = state.query;
    }
  }

  private renderScope(state: SearchViewState): void {
    const scopeEl = this.scopeEl;
    if (!scopeEl) {
      return;
    }
    scopeEl.empty();
    for (const option of state.scope.options) {
      const button = scopeEl.createEl("button", {
        cls: "prometheus-search-view__scope-btn",
        text: option.label,
      });
      button.toggleClass("is-active", option.mode === state.scope.selected);
      button.disabled = !option.enabled;
      if (option.reason) {
        button.title = option.reason;
      }
      button.addEventListener("click", () => {
        void this.store.setScopeMode(option.mode);
      });
    }
  }

  private renderStatus(state: SearchViewState): void {
    const statusEl = this.statusEl;
    if (!statusEl) {
      return;
    }
    if (state.status === "results") {
      statusEl.setText("");
      statusEl.hide();
      return;
    }
    statusEl.show();
    if (state.status === "error") {
      statusEl.setText(state.errorMessage ?? "Unable to search notes.");
      statusEl.addClass("is-error");
      return;
    }
    statusEl.removeClass("is-error");
    statusEl.setText(STATUS_COPY[state.status]);
  }

  private renderResults(state: SearchViewState): void {
    const resultsEl = this.resultsEl;
    if (!resultsEl) {
      return;
    }
    resultsEl.empty();
    if (state.status !== "results") {
      return;
    }
    for (const hit of state.hits) {
      this.renderHit(resultsEl, hit);
    }
  }

  private renderHit(parent: HTMLElement, hit: SearchHitDto): void {
    const row = parent.createDiv({
      cls: "prometheus-search-view__hit",
      attr: { tabindex: "0", role: "button" },
    });
    const header = row.createDiv({ cls: "prometheus-search-view__hit-header" });
    header.createSpan({
      cls: "prometheus-search-view__hit-score",
      text: hit.score.toFixed(2),
    });
    const title = hit.heading ? `${hit.path.value} › ${hit.heading}` : hit.path.value;
    header.createSpan({
      cls: "prometheus-search-view__hit-path",
      text: title,
    });
    const snippet = toPlainSnippet(hit.text);
    if (snippet.length > 0) {
      row.createDiv({
        cls: "prometheus-search-view__hit-snippet",
        text: snippet,
      });
    }
    const open = () => {
      void this.store.openHit(hit);
    };
    row.addEventListener("click", open);
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
  }
}
