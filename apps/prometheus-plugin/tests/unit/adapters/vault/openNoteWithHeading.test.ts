import { describe, expect, it } from "vitest";

import { openNoteWithHeading } from "../../../../src/adapters/outbound/vault/openNoteWithHeading";
import { NotePath } from "../../../../src/domain/value-objects/NotePath";
import { createMockApp } from "./mockApp";

describe("openNoteWithHeading", () => {
  it("opens with heading via openLinkText", async () => {
    const mock = createMockApp([{ path: "notes/a.md", content: "# Title\nbody" }]);
    await openNoteWithHeading(mock.app, NotePath.create("notes/a.md"), {
      heading: "Title",
      mode: "reuse_active",
    });
    expect(mock.openLinkCalls).toEqual([{ linktext: "notes/a.md#Title", newLeaf: false }]);
  });

  it("opens new pane only when target is not already active", async () => {
    const mock = createMockApp([{ path: "a.md", content: "x" }]);
    mock.setActiveFile("a.md");
    await openNoteWithHeading(mock.app, NotePath.create("a.md"), {
      mode: "open_new_pane",
    });
    expect(mock.openFileCalls).toEqual([{ path: "a.md", newLeaf: false }]);

    mock.openFileCalls.length = 0;
    mock.setActiveFile(null);
    await openNoteWithHeading(mock.app, NotePath.create("a.md"), {
      mode: "open_new_pane",
    });
    expect(mock.openFileCalls).toEqual([{ path: "a.md", newLeaf: true }]);
  });

  it("throws when note is missing", async () => {
    const mock = createMockApp();
    await expect(openNoteWithHeading(mock.app, NotePath.create("missing.md"))).rejects.toThrow(
      /not found/i,
    );
  });
});
