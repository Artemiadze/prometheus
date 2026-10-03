import { describe, expect, it, vi } from "vitest";

import { createEnsureRuntime } from "../../../src/bootstrap/ensureRuntime";
import { RuntimeStartFailedError } from "../../../src/domain/errors";

describe("createEnsureRuntime", () => {
  it("maps StartRuntime throws to a user-facing readiness failure", async () => {
    const ensureRuntime = createEnsureRuntime({
      execute: async () => {
        throw new RuntimeStartFailedError("port busy");
      },
    });
    const result = await ensureRuntime(new AbortController().signal);
    expect(result).toEqual({ ok: false, message: expect.stringContaining("port busy") });
  });

  it("does not throw when StartRuntime is aborted", async () => {
    const controller = new AbortController();
    controller.abort();
    const ensureRuntime = createEnsureRuntime({
      execute: async () => {
        throw new DOMException("The operation was aborted", "AbortError");
      },
    });
    const result = await ensureRuntime(controller.signal);
    expect(result).toEqual({ ok: false, message: "" });
  });

  it("calls onActivated when runtime becomes ready", async () => {
    const onActivated = vi.fn();
    const ensureRuntime = createEnsureRuntime(
      {
        execute: async () => ({
          kind: "ready" as const,
          runtime: { kind: "running" as const, version: "0.1.0" },
          connection: { baseUrl: "http://127.0.0.1:1", sessionToken: "t" },
          ownership: "owned" as const,
          spawned: true,
        }),
      },
      onActivated,
    );
    const result = await ensureRuntime(new AbortController().signal);
    expect(result).toEqual({ ok: true });
    expect(onActivated).toHaveBeenCalledOnce();
  });
});
