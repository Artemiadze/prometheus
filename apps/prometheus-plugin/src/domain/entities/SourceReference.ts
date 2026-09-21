import type { NotePath } from "../value-objects/NotePath";
import { NotePath as NotePathVo } from "../value-objects/NotePath";

/**
 * Navigable source in an Obsidian Vault (BR-5).
 * Display name never reveals an absolute path.
 */
export class SourceReference {
  readonly notePath: NotePath;
  readonly heading: string | null;

  private constructor(notePath: NotePath, heading: string | null) {
    this.notePath = notePath;
    this.heading = heading;
  }

  static create(notePath: NotePath | string, heading?: string | null): SourceReference {
    const path = notePath instanceof NotePathVo ? notePath : NotePathVo.create(notePath);
    const normalizedHeading =
      heading === undefined || heading === null ? null : heading.trim() || null;
    return new SourceReference(path, normalizedHeading);
  }

  get displayName(): string {
    if (this.heading === null) {
      return this.notePath.name;
    }
    return `${this.notePath.name} › ${this.heading}`;
  }

  get dedupeKey(): string {
    return `${this.notePath.value}#${this.heading ?? ""}`;
  }
}

/** Deduplicate by (path, heading), preserving first-seen order. */
export function dedupeSourceReferences(refs: readonly SourceReference[]): SourceReference[] {
  const seen = new Set<string>();
  const result: SourceReference[] = [];
  for (const ref of refs) {
    if (seen.has(ref.dedupeKey)) {
      continue;
    }
    seen.add(ref.dedupeKey);
    result.push(ref);
  }
  return result;
}
