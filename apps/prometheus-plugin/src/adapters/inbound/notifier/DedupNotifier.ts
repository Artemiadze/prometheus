import type { Clock } from "../../../application/ports/Clock";
import type { Notifier } from "../../../application/ports/Notifier";
import { sanitizeUserMessage } from "../obsidian/errors/sanitizeUserMessage";

const DEFAULT_WINDOW_MS = 30_000;

type DedupKey = string;

type DedupEntry = {
  lastEmittedAt: number;
  suppressed: number;
};

/**
 * Suppresses identical notices within a time window (PLG-74).
 * On the next allowed emit, appends " (repeated N times)" when suppressions occurred.
 */
export class DedupNotifier implements Notifier {
  private readonly windowMs: number;
  private readonly entries = new Map<DedupKey, DedupEntry>();

  constructor(
    private readonly inner: Notifier,
    private readonly clock: Clock,
    options?: { readonly windowMs?: number },
  ) {
    this.windowMs = options?.windowMs ?? DEFAULT_WINDOW_MS;
  }

  info(message: string): void {
    this.emit("info", message);
  }

  warning(message: string): void {
    this.emit("warning", message);
  }

  error(message: string): void {
    this.emit("error", message);
  }

  private emit(level: "info" | "warning" | "error", raw: string): void {
    const message = sanitizeUserMessage(raw);
    const key = `${level}|${message}`;
    const now = this.clock.now().getTime();
    const existing = this.entries.get(key);

    if (existing && now - existing.lastEmittedAt < this.windowMs) {
      existing.suppressed += 1;
      return;
    }

    const suppressed = existing?.suppressed ?? 0;
    const text = suppressed > 0 ? `${message} (repeated ${suppressed} times)` : message;
    this.inner[level](text);
    this.entries.set(key, { lastEmittedAt: now, suppressed: 0 });
  }
}
