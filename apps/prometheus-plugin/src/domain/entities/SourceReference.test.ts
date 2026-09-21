import { describe, expect, it } from "vitest";

import { NotePath } from "../value-objects/NotePath";
import { dedupeSourceReferences, SourceReference } from "./SourceReference";

describe("SourceReference", () => {
  it("builds a display name from the note file name without path segments", () => {
    const ref = SourceReference.create(NotePath.create("projects/work/plan.md"), "Goals");
    expect(ref.displayName).toBe("plan.md › Goals");
    expect(ref.displayName.includes("/")).toBe(false);
    expect(ref.displayName.includes("\\")).toBe(false);
  });

  it("normalizes blank headings to null", () => {
    const ref = SourceReference.create("notes/a.md", "   ");
    expect(ref.heading).toBeNull();
    expect(ref.displayName).toBe("a.md");
  });

  it("deduplicates by path and heading pair", () => {
    const a = SourceReference.create("a.md", "H1");
    const b = SourceReference.create("a.md", "H1");
    const c = SourceReference.create("a.md", "H2");
    const d = SourceReference.create("b.md", "H1");
    expect(dedupeSourceReferences([a, b, c, d])).toEqual([a, c, d]);
  });
});
