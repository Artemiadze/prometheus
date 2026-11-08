/**
 * Obsidian scanner requires window.setTimeout / window.clearTimeout for popout
 * compatibility. Vitest runs in Node, so mirror timers onto globalThis.window.
 */
if (typeof (globalThis as { window?: unknown }).window === "undefined") {
  Object.defineProperty(globalThis, "window", {
    value: globalThis,
    configurable: true,
    writable: true,
  });
}
