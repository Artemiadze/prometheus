import type {
  LogFields,
  Logger,
  RecentEventsReader,
  RecentLogEvent,
} from "../../../application/ports/Logger";
import type { Clock } from "../../../application/ports/Clock";
import { sanitizeLogFields } from "../../../application/services/sanitizeLogFields";

const DEFAULT_MAX_EVENTS = 100;

/**
 * In-memory ring buffer of structured log events for the diagnostics report.
 */
export class RecentEventsBuffer implements Logger, RecentEventsReader {
  private readonly events: RecentLogEvent[] = [];
  private readonly maxEvents: number;

  constructor(
    private readonly clock: Clock,
    options?: { readonly maxEvents?: number },
  ) {
    this.maxEvents = options?.maxEvents ?? DEFAULT_MAX_EVENTS;
  }

  event(name: string, fields?: LogFields): void {
    this.push("event", name, fields);
  }

  error(code: string, fields?: LogFields): void {
    this.push("error", code, fields);
  }

  debug(name: string, fields?: LogFields): void {
    this.push("debug", name, fields);
  }

  snapshot(): readonly RecentLogEvent[] {
    return [...this.events];
  }

  clear(): void {
    this.events.length = 0;
  }

  private push(level: RecentLogEvent["level"], name: string, fields: LogFields | undefined): void {
    this.events.push({
      at: this.clock.now(),
      level,
      name,
      fields: sanitizeLogFields(fields),
    });
    while (this.events.length > this.maxEvents) {
      this.events.shift();
    }
  }
}
