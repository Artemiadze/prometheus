import type { SearchScopePreference } from "../../../../application/dto/settings";
import type { NotePath } from "../../../../domain/value-objects/NotePath";
import { SearchScope } from "../../../../domain/value-objects/SearchScope";

export type ScopeOption = {
  readonly mode: SearchScopePreference;
  readonly label: string;
  readonly enabled: boolean;
  readonly reason: string | null;
};

export type ScopeOptionsState = {
  readonly selected: SearchScopePreference;
  readonly options: readonly ScopeOption[];
};

export function buildScopeOptions(
  activeNote: NotePath | null,
  activeFolder: NotePath | null,
): readonly ScopeOption[] {
  const noActiveNote = activeNote === null;
  const noteInRoot = activeNote !== null && activeFolder === null;

  return [
    {
      mode: "entire_vault",
      label: "Entire vault",
      enabled: true,
      reason: null,
    },
    {
      mode: "current_folder",
      label: "Current folder",
      enabled: !noActiveNote && !noteInRoot,
      reason: noActiveNote
        ? "Open a note to use this scope"
        : noteInRoot
          ? "Active note is in the vault root"
          : null,
    },
    {
      mode: "current_note",
      label: "Current note",
      enabled: !noActiveNote,
      reason: noActiveNote ? "Open a note to use this scope" : null,
    },
  ];
}

export function resolveScope(
  mode: SearchScopePreference,
  activeNote: NotePath | null,
  activeFolder: NotePath | null,
): SearchScope {
  const options = buildScopeOptions(activeNote, activeFolder);
  const selected = options.find((option) => option.mode === mode);
  if (!selected?.enabled) {
    return SearchScope.entireVault();
  }
  switch (mode) {
    case "entire_vault":
      return SearchScope.entireVault();
    case "current_folder":
      return SearchScope.currentFolder(activeFolder!);
    case "current_note":
      return SearchScope.currentNote(activeNote!);
    default: {
      const _exhaustive: never = mode;
      return _exhaustive;
    }
  }
}

export function createScopeOptionsState(
  selected: SearchScopePreference,
  activeNote: NotePath | null,
  activeFolder: NotePath | null,
): ScopeOptionsState {
  return {
    selected,
    options: buildScopeOptions(activeNote, activeFolder),
  };
}
