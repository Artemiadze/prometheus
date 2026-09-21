/**
 * Time source for debounce and scheduling. Fakes advance virtual time in tests.
 */
export interface Clock {
  now(): Date;
  sleep(ms: number, signal?: AbortSignal): Promise<void>;
}
