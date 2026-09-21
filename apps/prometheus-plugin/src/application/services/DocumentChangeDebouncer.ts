import type { VaultEvent } from "../dto/vault";
import type { Clock } from "../ports/Clock";

export type DocumentChangeSyncExecutor = {
  execute(event: VaultEvent, signal?: AbortSignal): Promise<void>;
};

type PendingEntry = {
  event: VaultEvent;
  controller: AbortController;
  timer: Promise<void>;
};

/**
 * Per-path debounce + global concurrency queue for vault change → SyncDocumentChange.
 */
export class DocumentChangeDebouncer {
  private readonly pending = new Map<string, PendingEntry>();
  private readonly queue: Array<() => void> = [];
  private active = 0;
  private debounceMs: number;
  private maxConcurrent: number;

  constructor(
    private readonly sync: DocumentChangeSyncExecutor,
    private readonly clock: Clock,
    options: { debounceMs?: number; maxConcurrent?: number } = {},
  ) {
    this.debounceMs = options.debounceMs ?? 750;
    this.maxConcurrent = options.maxConcurrent ?? 2;
  }

  configure(options: { debounceMs?: number; maxConcurrent?: number }): void {
    if (options.debounceMs !== undefined) {
      this.debounceMs = options.debounceMs;
    }
    if (options.maxConcurrent !== undefined) {
      this.maxConcurrent = options.maxConcurrent;
    }
  }

  /** Enqueue a vault event; last event per path wins after debounce. */
  enqueue(event: VaultEvent): void {
    const key = debounceKey(event);

    if (event.type === "rename") {
      this.cancelPath(event.previousPath.value);
    }

    const existing = this.pending.get(key);
    if (existing) {
      existing.controller.abort();
      this.pending.delete(key);
    }

    const controller = new AbortController();
    const timer = this.clock
      .sleep(this.debounceMs, controller.signal)
      .then(() => {
        const current = this.pending.get(key);
        if (!current || current.controller !== controller) {
          return;
        }
        this.pending.delete(key);
        return this.runSync(current.event);
      })
      .catch((error: unknown) => {
        if (isAbortError(error)) {
          return;
        }
        throw error;
      });

    this.pending.set(key, { event, controller, timer });
  }

  /** Wait until all debounced work and in-flight syncs finish (tests). */
  async flush(): Promise<void> {
    while (this.pending.size > 0 || this.active > 0 || this.queue.length > 0) {
      const timers = [...this.pending.values()].map((entry) => entry.timer);
      if (timers.length > 0) {
        await Promise.allSettled(timers);
      } else {
        await Promise.resolve();
      }
    }
  }

  private cancelPath(pathValue: string): void {
    const existing = this.pending.get(pathValue);
    if (existing) {
      existing.controller.abort();
      this.pending.delete(pathValue);
    }
  }

  private async runSync(event: VaultEvent): Promise<void> {
    await this.acquire();
    try {
      await this.sync.execute(event);
    } finally {
      this.release();
    }
  }

  private async acquire(): Promise<void> {
    if (this.active < this.maxConcurrent) {
      this.active += 1;
      return;
    }
    await new Promise<void>((resolve) => {
      this.queue.push(() => {
        this.active += 1;
        resolve();
      });
    });
  }

  private release(): void {
    this.active -= 1;
    const next = this.queue.shift();
    if (next) {
      next();
    }
  }
}

function debounceKey(event: VaultEvent): string {
  return event.path.value;
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}
