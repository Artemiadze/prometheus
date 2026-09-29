import type { LogFields, LoggerWithVerbose } from "../../../application/ports/Logger";
import { sanitizeLogFields } from "../../../application/services/sanitizeLogFields";

export type ConsoleSink = {
  debug: (...args: unknown[]) => void;
  info: (...args: unknown[]) => void;
  error: (...args: unknown[]) => void;
};

/**
 * Console sink for structured Prometheus events (PLG-76).
 * `debug` is gated by verbose mode.
 */
export class ConsoleLogger implements LoggerWithVerbose {
  private verbose = false;

  constructor(private readonly sink: ConsoleSink = console) {}

  setVerbose(enabled: boolean): void {
    this.verbose = enabled;
  }

  isVerbose(): boolean {
    return this.verbose;
  }

  event(name: string, fields?: LogFields): void {
    this.sink.info("[prometheus]", name, sanitizeLogFields(fields));
  }

  error(code: string, fields?: LogFields): void {
    this.sink.error("[prometheus]", code, sanitizeLogFields(fields));
  }

  debug(name: string, fields?: LogFields): void {
    if (!this.verbose) {
      return;
    }
    this.sink.debug("[prometheus]", name, sanitizeLogFields(fields));
  }
}
