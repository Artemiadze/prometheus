import type { Clock } from "../../../application/ports/Clock";

export class SystemClock implements Clock {
  now(): Date {
    return new Date();
  }

  sleep(ms: number, signal?: AbortSignal): Promise<void> {
    if (signal?.aborted) {
      return Promise.reject(new DOMException("The operation was aborted", "AbortError"));
    }
    return new Promise((resolve, reject) => {
      const timer = window.setTimeout(() => {
        cleanup();
        resolve();
      }, ms);
      const onAbort = () => {
        cleanup();
        reject(new DOMException("The operation was aborted", "AbortError"));
      };
      const cleanup = () => {
        window.clearTimeout(timer);
        signal?.removeEventListener("abort", onAbort);
      };
      signal?.addEventListener("abort", onAbort, { once: true });
    });
  }
}
