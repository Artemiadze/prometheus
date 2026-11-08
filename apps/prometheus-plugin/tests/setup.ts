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

/** Obsidian cross-window type guard used by prefer-instanceof (DOM envs only). */
if (
  typeof HTMLElement !== "undefined" &&
  typeof (HTMLElement.prototype as { instanceOf?: unknown }).instanceOf !== "function"
) {
  Object.defineProperty(Node.prototype, "instanceOf", {
    value: function instanceOf(this: Node, type: new (...args: never[]) => unknown): boolean {
      return this instanceof type;
    },
    configurable: true,
  });
}

/** Obsidian DOM helpers are ambient globals in the app; expose them when DOM exists. */
if (
  typeof document !== "undefined" &&
  typeof (globalThis as { createDiv?: unknown }).createDiv !== "function"
) {
  (globalThis as { createDiv: (o?: unknown) => HTMLDivElement }).createDiv = (o) => {
    const el = document.createElement("div");
    if (typeof o === "string") {
      el.className = o;
    } else if (o && typeof o === "object") {
      const opts = o as { cls?: string | string[]; text?: string };
      if (typeof opts.cls === "string") {
        el.className = opts.cls;
      } else if (Array.isArray(opts.cls)) {
        el.className = opts.cls.join(" ");
      }
      if (typeof opts.text === "string") {
        el.textContent = opts.text;
      }
    }
    return el;
  };
}
