import type { Clock } from "../../src/application/ports/Clock";

type SleepWaiter = {
  resolveAt: number;
  resolve: () => void;
  reject: (error: Error) => void;
  signal?: AbortSignal;
  onAbort?: () => void;
};

/**
 * Controllable clock: sleep waits until advance() moves virtual time past the deadline.
 */
export class FakeClock implements Clock {
  private currentMs: number;
  private readonly waiters: SleepWaiter[] = [];

  constructor(start: Date = new Date(0)) {
    this.currentMs = start.getTime();
  }

  now(): Date {
    return new Date(this.currentMs);
  }

  async sleep(ms: number, signal?: AbortSignal): Promise<void> {
    if (ms <= 0) {
      return;
    }
    if (signal?.aborted) {
      throw abortError();
    }
    const resolveAt = this.currentMs + ms;
    return new Promise<void>((resolve, reject) => {
      const waiter: SleepWaiter = { resolveAt, resolve, reject };
      if (signal) {
        waiter.signal = signal;
        const onAbort = (): void => {
          this.removeWaiter(waiter);
          reject(abortError());
        };
        waiter.onAbort = onAbort;
        signal.addEventListener("abort", onAbort, { once: true });
      }
      this.waiters.push(waiter);
      this.flushWaiters();
    });
  }

  /** Advance virtual time by `ms` and resolve due sleepers. */
  advance(ms: number): void {
    if (ms < 0) {
      throw new Error("Cannot advance clock backwards");
    }
    this.currentMs += ms;
    this.flushWaiters();
  }

  private flushWaiters(): void {
    const due = this.waiters.filter((w) => w.resolveAt <= this.currentMs);
    for (const waiter of due) {
      this.removeWaiter(waiter);
      if (waiter.signal?.aborted) {
        waiter.reject(abortError());
      } else {
        waiter.resolve();
      }
    }
  }

  private removeWaiter(waiter: SleepWaiter): void {
    const index = this.waiters.indexOf(waiter);
    if (index >= 0) {
      this.waiters.splice(index, 1);
    }
    if (waiter.signal && waiter.onAbort) {
      waiter.signal.removeEventListener("abort", waiter.onAbort);
    }
  }
}

function abortError(): Error {
  return new DOMException("The operation was aborted", "AbortError");
}
