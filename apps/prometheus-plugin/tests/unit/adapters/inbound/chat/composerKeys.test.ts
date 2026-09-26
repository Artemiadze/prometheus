import { describe, expect, it } from "vitest";

import { resolveComposerKey } from "../../../../../src/adapters/inbound/obsidian/chat/composerKeys";

describe("resolveComposerKey", () => {
  it("maps Enter and Shift+Enter", () => {
    expect(resolveComposerKey({ key: "Enter", shiftKey: false })).toBe("send");
    expect(resolveComposerKey({ key: "Enter", shiftKey: true })).toBe("newline");
  });

  it("ignores IME composition", () => {
    expect(resolveComposerKey({ key: "Enter", shiftKey: false, isComposing: true })).toBe("ignore");
  });
});
