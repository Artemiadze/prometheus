/**
 * Structured plugin logger. Accepts only event names, error codes and short
 * primitive fields — never free-text note content (PLG-76).
 */
export type LogFields = Readonly<Record<string, string | number | boolean>>;

export interface Logger {
  event(name: string, fields?: LogFields): void;
  error(code: string, fields?: LogFields): void;
  debug(name: string, fields?: LogFields): void;
}

export type LoggerWithVerbose = Logger & {
  setVerbose(enabled: boolean): void;
  isVerbose(): boolean;
};

export type RecentLogEvent = {
  readonly at: Date;
  readonly level: "event" | "error" | "debug";
  readonly name: string;
  readonly fields: LogFields;
};

export interface RecentEventsReader {
  snapshot(): readonly RecentLogEvent[];
}
