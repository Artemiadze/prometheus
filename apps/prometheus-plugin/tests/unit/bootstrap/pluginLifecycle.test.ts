import { describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import {
  createActivationGate,
  detachPluginLeaves,
  PLUGIN_VIEW_TYPES,
} from "../../../src/bootstrap/pluginLifecycle";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../..");

describe("createActivationGate", () => {
  it("is idempotent: starts polling and auto-index once", () => {
    const startPolling = vi.fn();
    const applySettingsEnabled = vi.fn();
    const gate = createActivationGate({
      statusStore: { startPolling },
      autoIndexing: { applySettingsEnabled },
    });

    expect(gate.isActivated()).toBe(false);
    gate.activate();
    gate.activate();
    expect(gate.isActivated()).toBe(true);
    expect(startPolling).toHaveBeenCalledOnce();
    expect(applySettingsEnabled).toHaveBeenCalledOnce();
  });
});

describe("detachPluginLeaves", () => {
  it("detaches chat, search, and status leaves", () => {
    const detachLeavesOfType = vi.fn();
    detachPluginLeaves({ workspace: { detachLeavesOfType } });
    expect(detachLeavesOfType.mock.calls.map((c: unknown[]) => c[0])).toEqual([
      ...PLUGIN_VIEW_TYPES,
    ]);
  });
});

describe("compositionBoundaries", () => {
  it("views do not import outbound adapters", () => {
    const viewsDir = join(root, "src/adapters/inbound/obsidian/views");
    const files = ["ChatView.ts", "SearchView.ts", "StatusView.ts"];
    for (const file of files) {
      const source = readFileSync(join(viewsDir, file), "utf8");
      expect(source, file).not.toMatch(/adapters\/outbound/);
    }
  });
});
