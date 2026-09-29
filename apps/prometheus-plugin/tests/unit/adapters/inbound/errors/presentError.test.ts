import { describe, expect, it } from "vitest";

import { presentError } from "../../../../../src/adapters/inbound/obsidian/errors/presentError";
import { sanitizeUserMessage } from "../../../../../src/adapters/inbound/obsidian/errors/sanitizeUserMessage";
import {
  RuntimeApiError,
  RuntimeNotInstalledError,
  RuntimeStartTimeoutError,
} from "../../../../../src/domain/errors";

describe("sanitizeUserMessage", () => {
  it("strips stack frames and absolute paths", () => {
    const raw = [
      "Failed at something",
      "    at Object.<anonymous> (/home/user/obsidian_copilot/main.js:10:5)",
      "Error: boom",
      "C:\\Users\\artyom\\vault\\note.md",
    ].join("\n");
    const cleaned = sanitizeUserMessage(raw);
    expect(cleaned).not.toContain("/home/user");
    expect(cleaned).not.toContain("C:\\Users");
    expect(cleaned).not.toContain("at Object");
    expect(cleaned).not.toMatch(/:\d+:\d+/);
  });
});

describe("presentError", () => {
  it("maps plugin errors to catalog copy", () => {
    const presented = presentError(new RuntimeNotInstalledError());
    expect(presented.code).toBe("RUNTIME_NOT_INSTALLED");
    expect(presented.message).toContain("not installed");
    expect(presented.message.toLowerCase()).toContain("no cloud");
    expect(presented.requestId).toBeNull();
  });

  it("preserves RuntimeApiError requestId and recommended action", () => {
    const presented = presentError(
      new RuntimeApiError({
        code: "OLLAMA_UNAVAILABLE",
        runtimeCode: "OLLAMA_UNAVAILABLE",
        message: "ignored raw message",
        requestId: "req-123",
        httpStatus: 503,
        recommendedAction: "restart_runtime",
      }),
    );
    expect(presented.code).toBe("OLLAMA_UNAVAILABLE");
    expect(presented.requestId).toBe("req-123");
    expect(presented.action).toBe("restart_runtime");
    expect(presented.message).not.toContain("ignored raw message");
  });

  it("never surfaces stack traces or absolute paths from unknown errors", () => {
    const err = new Error("boom at /home/user/secret/file.ts:12:3");
    err.stack = `Error: boom\n    at fail (/home/user/secret/file.ts:12:3)`;
    const presented = presentError(err);
    expect(presented.code).toBe("UNKNOWN");
    expect(presented.message).not.toContain("/home/user");
    expect(presented.message).not.toContain("at fail");
    expect(presented.message).not.toContain("boom");
    expect(presented.action).toBe("open_diagnostics");
  });

  it("maps start timeout to open_diagnostics", () => {
    const presented = presentError(new RuntimeStartTimeoutError());
    expect(presented.code).toBe("RUNTIME_START_TIMEOUT");
    expect(presented.action).toBe("open_diagnostics");
  });
});
