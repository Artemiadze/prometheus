const DEFAULT_MAX_LINES = 200;
const DEFAULT_MAX_LINE_LENGTH = 2_048;

export class DiagnosticBuffer {
  private readonly lines: string[] = [];
  private readonly maxLines: number;
  private readonly maxLineLength: number;

  constructor(options?: { readonly maxLines?: number; readonly maxLineLength?: number }) {
    this.maxLines = options?.maxLines ?? DEFAULT_MAX_LINES;
    this.maxLineLength = options?.maxLineLength ?? DEFAULT_MAX_LINE_LENGTH;
  }

  append(stream: "stdout" | "stderr", chunk: string): void {
    const prefix = stream === "stdout" ? "[stdout] " : "[stderr] ";
    const parts = chunk.split(/\r?\n/);
    for (const part of parts) {
      if (part.length === 0) {
        continue;
      }
      const sanitized = sanitizeLine(part);
      const line = prefix + truncate(sanitized, this.maxLineLength);
      this.lines.push(line);
      while (this.lines.length > this.maxLines) {
        this.lines.shift();
      }
    }
  }

  snapshot(): readonly string[] {
    return [...this.lines];
  }

  clear(): void {
    this.lines.length = 0;
  }
}

export function maskArgvForDiagnostics(argv: readonly string[]): string {
  const masked: string[] = [];
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index] ?? "";
    if (token === "--session-token") {
      masked.push(token, "***");
      index += 1;
      continue;
    }
    if (token.startsWith("--session-token=")) {
      masked.push("--session-token=***");
      continue;
    }
    masked.push(token);
  }
  return masked.join(" ");
}

function sanitizeLine(line: string): string {
  return line.replace(/Bearer\s+\S+/gi, "Bearer ***");
}

function truncate(value: string, maxLength: number): string {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength)}…`;
}
