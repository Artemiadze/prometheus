import { afterEach, describe, expect, it, vi } from "vitest";

import { RuntimeHttpClient } from "../../../../src/adapters/outbound/rag-api/RuntimeHttpClient";
import { RuntimeSessionRegistry } from "../../../../src/application/services/RuntimeSessionRegistry";
import {
  RuntimeApiError,
  RuntimeContractError,
  RuntimeRequestTimeoutError,
} from "../../../../src/domain/errors";

describe("RuntimeHttpClient", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("keeps health unauthenticated and adds protected diagnostic headers", async () => {
    const sessions = activeSessions("secret-session-token");
    const calls: Array<{ url: string; init: RequestInit }> = [];
    const fetchFn: typeof fetch = async (input, init = {}) => {
      if (typeof input !== "string") {
        throw new Error("Expected string URL");
      }
      calls.push({ url: input, init });
      return jsonResponse({ ok: true });
    };
    const client = new RuntimeHttpClient({
      sessions,
      getHealthBaseUrl: () => "http://127.0.0.1:8765",
      fetchFn,
      requestIdFactory: () => "request-1",
      pluginVersion: "0.1.0",
    });

    await client.request("/health", {
      protected: false,
      decode: () => true,
    });
    await client.request("/models", {
      decode: () => true,
    });

    expect(calls.map((call) => call.url)).toEqual([
      "http://127.0.0.1:8765/v1/health",
      "http://127.0.0.1:8765/v1/models",
    ]);
    const healthHeaders = new Headers(calls[0]?.init.headers);
    expect(healthHeaders.has("Authorization")).toBe(false);
    expect(healthHeaders.has("X-Request-ID")).toBe(false);

    const protectedHeaders = new Headers(calls[1]?.init.headers);
    expect(protectedHeaders.get("Authorization")).toBe("Bearer secret-session-token");
    expect(protectedHeaders.get("X-Request-ID")).toBe("request-1");
    expect(protectedHeaders.get("X-Prometheus-Plugin-Version")).toBe("0.1.0");
  });

  it("maps 401, clears the session and never exposes the token", async () => {
    const sessions = activeSessions("do-not-leak");
    let unauthorizedCalls = 0;
    const client = new RuntimeHttpClient({
      sessions,
      getHealthBaseUrl: () => "http://127.0.0.1:8765",
      fetchFn: async () =>
        jsonResponse(
          {
            error: {
              code: "UNAUTHORIZED",
              message: "bad credentials",
              request_id: "runtime-request",
            },
          },
          401,
        ),
      onUnauthorized: () => {
        unauthorizedCalls += 1;
      },
    });

    const error = await client
      .request("/models", { decode: () => true })
      .catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(RuntimeApiError);
    expect(error).toMatchObject({
      code: "UNAUTHORIZED",
      requestId: "runtime-request",
      recommendedAction: "reinitialize_runtime",
    });
    expect((error as Error).message).not.toContain("do-not-leak");
    expect(sessions.get()).toBeNull();
    expect(unauthorizedCalls).toBe(1);
  });

  it("preserves request id for unknown runtime errors", async () => {
    const client = new RuntimeHttpClient({
      sessions: activeSessions("secret"),
      getHealthBaseUrl: () => "http://127.0.0.1:8765",
      fetchFn: async () =>
        jsonResponse(
          {
            error: {
              code: "FUTURE_ERROR",
              message: "future detail",
              request_id: "future-request",
            },
          },
          500,
        ),
    });

    const error = await client
      .request("/models", { decode: () => true })
      .catch((caught: unknown) => caught);
    expect(error).toMatchObject({
      code: "RUNTIME_API_ERROR",
      runtimeCode: "FUTURE_ERROR",
      requestId: "future-request",
      recommendedAction: "open_diagnostics",
    });
  });

  it("reports malformed JSON as a contract error", async () => {
    const client = new RuntimeHttpClient({
      sessions: activeSessions("secret"),
      getHealthBaseUrl: () => "http://127.0.0.1:8765",
      fetchFn: async () =>
        new Response("{broken", {
          status: 200,
          headers: { "X-Request-ID": "parse-request" },
        }),
    });

    const error = await client
      .request("/models", { decode: () => true })
      .catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(RuntimeContractError);
    expect(error).toMatchObject({ requestId: "parse-request" });
  });

  it("distinguishes timeout from caller cancellation", async () => {
    vi.useFakeTimers();
    const fetchFn: typeof fetch = async (_input, init = {}) =>
      new Promise<Response>((_resolve, reject) => {
        init.signal?.addEventListener(
          "abort",
          () => {
            reject(new DOMException("aborted", "AbortError"));
          },
          { once: true },
        );
      });
    const client = new RuntimeHttpClient({
      sessions: activeSessions("secret"),
      getHealthBaseUrl: () => "http://127.0.0.1:8765",
      fetchFn,
      timeoutMs: 50,
    });

    const timedOut = client
      .request("/models", { decode: () => true })
      .catch((caught: unknown) => caught);
    await vi.advanceTimersByTimeAsync(50);
    expect(await timedOut).toBeInstanceOf(RuntimeRequestTimeoutError);

    const controller = new AbortController();
    const cancelled = client
      .request("/models", { signal: controller.signal, decode: () => true })
      .catch((caught: unknown) => caught);
    controller.abort();
    const cancelError = await cancelled;
    expect(cancelError).toBeInstanceOf(DOMException);
    expect((cancelError as DOMException).name).toBe("AbortError");
  });

  it("rejects non-loopback base URLs before fetch", async () => {
    const fetchFn = vi.fn<typeof fetch>();
    const client = new RuntimeHttpClient({
      sessions: new RuntimeSessionRegistry(),
      getHealthBaseUrl: () => "https://example.com",
      fetchFn,
    });
    await expect(
      client.request("/health", { protected: false, decode: () => true }),
    ).rejects.toBeInstanceOf(RuntimeContractError);
    expect(fetchFn).not.toHaveBeenCalled();
  });
});

function activeSessions(token: string): RuntimeSessionRegistry {
  const sessions = new RuntimeSessionRegistry();
  sessions.set({
    ownership: "owned",
    connection: {
      baseUrl: "http://127.0.0.1:8765",
      sessionToken: token,
    },
  });
  return sessions;
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
