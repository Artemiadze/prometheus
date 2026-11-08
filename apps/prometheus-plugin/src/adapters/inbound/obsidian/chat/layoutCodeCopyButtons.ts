/**
 * Place Obsidian's code-block copy control on the same row as the command,
 * aligned to the right of the fenced block.
 */
export function layoutCodeCopyButtons(root: HTMLElement): void {
  const blocks = Array.from(root.querySelectorAll("pre"));
  for (const pre of blocks) {
    if (pre.closest(".prometheus-chat-code")) {
      continue;
    }

    const parent = pre.parentElement;
    if (!parent) {
      continue;
    }

    const innerButton = findCopyButton(pre);
    const siblingButton =
      innerButton === null && pre.nextElementSibling?.instanceOf(HTMLElement)
        ? asCopyButton(pre.nextElementSibling)
        : null;
    const button = innerButton ?? siblingButton;
    if (button === null) {
      continue;
    }

    const wrap = createDiv({ cls: "prometheus-chat-code" });
    parent.insertBefore(wrap, pre);
    wrap.appendChild(pre);
    wrap.appendChild(button);
  }
}

function findCopyButton(pre: HTMLElement): HTMLElement | null {
  for (const child of Array.from(pre.children)) {
    if (!child.instanceOf(HTMLElement)) {
      continue;
    }
    const match = asCopyButton(child);
    if (match !== null) {
      return match;
    }
  }
  return null;
}

function asCopyButton(el: HTMLElement): HTMLElement | null {
  if (el.tagName !== "BUTTON") {
    return null;
  }
  if (el.classList.contains("copy-code-button")) {
    return el;
  }
  const label = (el.getAttribute("aria-label") ?? el.getAttribute("title") ?? "").toLowerCase();
  if (label.includes("copy")) {
    return el;
  }
  return null;
}
