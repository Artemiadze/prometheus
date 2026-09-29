import type { LogFields, Logger, LoggerWithVerbose } from "../../../application/ports/Logger";

/**
 * Fans out log calls to console + recent-events buffer.
 */
export class CompositeLogger implements LoggerWithVerbose {
  private verbose = false;

  constructor(
    private readonly sinks: readonly Logger[],
    private readonly verboseTargets: readonly LoggerWithVerbose[] = [],
  ) {}

  setVerbose(enabled: boolean): void {
    this.verbose = enabled;
    for (const target of this.verboseTargets) {
      target.setVerbose(enabled);
    }
  }

  isVerbose(): boolean {
    return this.verbose;
  }

  event(name: string, fields?: LogFields): void {
    for (const sink of this.sinks) {
      sink.event(name, fields);
    }
  }

  error(code: string, fields?: LogFields): void {
    for (const sink of this.sinks) {
      sink.error(code, fields);
    }
  }

  debug(name: string, fields?: LogFields): void {
    for (const sink of this.sinks) {
      sink.debug(name, fields);
    }
  }
}
