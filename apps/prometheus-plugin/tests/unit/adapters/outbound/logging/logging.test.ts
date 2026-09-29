import { describe, expect, it, vi } from "vitest";

import { ErrorReporter } from "../../../../../src/adapters/inbound/obsidian/errors/ErrorReporter";
import {
  CompositeLogger,
  ConsoleLogger,
  RecentEventsBuffer,
} from "../../../../../src/adapters/outbound/logging";
import { RuntimeNotInstalledError } from "../../../../../src/domain/errors";
import { FakeClock } from "../../../../fakes/FakeClock";
import { FakeNotifier } from "../../../../fakes/FakeNotifier";

describe("logging privacy", () => {
  it("never writes note text, queries, or session tokens to the console", () => {
    const info = vi.fn();
    const error = vi.fn();
    const debug = vi.fn();
    const consoleLogger = new ConsoleLogger({ info, error, debug });
    const recent = new RecentEventsBuffer(new FakeClock());
    const logger = new CompositeLogger([consoleLogger, recent], [consoleLogger]);

    expect(logger.isVerbose()).toBe(false);

    logger.event("runtime.started", {
      version: "1.0.0",
      sessionToken: "super-secret-token-value",
      query: "search my private notes about salary",
      note: "This is the full body of my daily note with secrets.",
      content: "more note content",
    });
    logger.error("RUNTIME_API_ERROR", {
      requestId: "req-1",
      text: "assistant said something private",
    });
    logger.debug("chat.payload", { query: "should stay silent" });

    expect(debug).not.toHaveBeenCalled();
    const serialized = JSON.stringify([info.mock.calls, error.mock.calls]);
    expect(serialized).not.toContain("salary");
    expect(serialized).not.toContain("daily note");
    expect(serialized).not.toContain("super-secret");
    expect(serialized).not.toContain("assistant said");
    expect(serialized).toContain("runtime.started");
    expect(serialized).toContain("RUNTIME_API_ERROR");
    expect(serialized).toContain("req-1");

    logger.setVerbose(true);
    logger.debug("verbose.only", { requestId: "req-2" });
    expect(debug).toHaveBeenCalledTimes(1);
    expect(JSON.stringify(debug.mock.calls)).not.toContain("salary");
  });

  it("ErrorReporter logs codes without raw note bodies", () => {
    const info = vi.fn();
    const error = vi.fn();
    const debug = vi.fn();
    const consoleLogger = new ConsoleLogger({ info, error, debug });
    const notifier = new FakeNotifier();
    const reporter = new ErrorReporter({ notifier, logger: consoleLogger });

    const presented = reporter.report(
      new Error("Failed reading /home/user/vault/Secret note.md with body: my private thoughts"),
    );
    expect(presented.code).toBe("UNKNOWN");
    expect(presented.message).not.toContain("private thoughts");
    expect(presented.message).not.toContain("/home/user");

    const serialized = JSON.stringify(error.mock.calls);
    expect(serialized).not.toContain("private thoughts");
    expect(serialized).toContain("UNKNOWN");

    reporter.report(new RuntimeNotInstalledError());
    expect(notifier.records.some((r) => r.message.toLowerCase().includes("not installed"))).toBe(
      true,
    );
  });
});
