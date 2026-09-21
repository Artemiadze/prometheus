import { InvalidSearchScopeError } from "../errors";
import { NotePath } from "./NotePath";

export type ScopeMode = "entire_vault" | "current_note" | "current_folder" | "selected_folders";

export type SearchScopePayload = {
  mode: ScopeMode;
  note: string | null;
  folders: string[];
};

/**
 * Validated retrieval scope (BR-11). Mirrors runtime SearchScope and
 * OpenAPI SearchScopeRequest serialization.
 */
export class SearchScope {
  readonly mode: ScopeMode;
  readonly note: NotePath | null;
  readonly folders: readonly NotePath[];

  private constructor(mode: ScopeMode, note: NotePath | null, folders: readonly NotePath[]) {
    this.mode = mode;
    this.note = note;
    this.folders = folders;
  }

  static entireVault(): SearchScope {
    return new SearchScope("entire_vault", null, []);
  }

  static currentNote(path: NotePath | string): SearchScope {
    return new SearchScope("current_note", toPath(path), []);
  }

  static currentFolder(folder: NotePath | string): SearchScope {
    return new SearchScope("current_folder", null, [toPath(folder)]);
  }

  static selectedFolders(folders: readonly (NotePath | string)[]): SearchScope {
    const unique = dedupePaths(folders.map(toPath));
    if (unique.length === 0) {
      throw new InvalidSearchScopeError();
    }
    return new SearchScope("selected_folders", null, unique);
  }

  serialize(): SearchScopePayload {
    return {
      mode: this.mode,
      note: this.note?.value ?? null,
      folders: this.folders.map((folder) => folder.value),
    };
  }
}

function toPath(value: NotePath | string): NotePath {
  return value instanceof NotePath ? value : NotePath.create(value);
}

function dedupePaths(paths: readonly NotePath[]): NotePath[] {
  const seen = new Set<string>();
  const result: NotePath[] = [];
  for (const path of paths) {
    if (seen.has(path.value)) {
      continue;
    }
    seen.add(path.value);
    result.push(path);
  }
  return result;
}
