import { createServer, type ServerResponse } from "node:http";
import type { AddressInfo } from "node:net";

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
    expect(await timedOut).toMatchObject({ timeoutMs: 50 });

    const longTimedOut = client
      .request("/models", { timeoutMs: 200, decode: () => true })
      .catch((caught: unknown) => caught);
    await vi.advanceTimersByTimeAsync(199);
    // Still pending before per-request timeout.
    let settled = false;
    void longTimedOut.then(() => {
      settled = true;
    });
    await Promise.resolve();
    expect(settled).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    expect(await longTimedOut).toMatchObject({ timeoutMs: 200 });

    const controller = new AbortController();
    const cancelled = client
      .request("/models", { signal: controller.signal, decode: () => true })
      .catch((caught: unknown) => caught);
    controller.abort();
    const cancelError = await cancelled;
    expect(cancelError).toBeInstanceOf(DOMException);
    expect((cancelError as DOMException).name).toBe("AbortError");
  });

  it("treats the stream timeout as idle time between NDJSON lines", async () => {
    const server = await startServer((response) => {
      response.writeHead(200, { "Content-Type": "application/x-ndjson" });
      let sent = 0;
      const interval = setInterval(() => {
        sent += 1;
        response.write(`{"type":"heartbeat","n":${sent}}\n`);
        if (sent === 5) {
          clearInterval(interval);
          response.end();
        }
      }, 30);
    });
    try {
      const client = new RuntimeHttpClient({
        sessions: activeSessions("secret", server.baseUrl),
        getHealthBaseUrl: () => server.baseUrl,
      });
      const lines: string[] = [];
      await client.streamNdjson("/stream", {
        timeoutMs: 100,
        onLine: (line) => lines.push(line),
      });
      expect(lines).toHaveLength(5);
    } finally {
      await server.close();
    }
  });

  it("times out a stream that stays silent", async () => {
    const server = await startServer((response) => {
      response.writeHead(200, { "Content-Type": "application/x-ndjson" });
      response.write('{"type":"heartbeat"}\n');
    });
    try {
      const client = new RuntimeHttpClient({
        sessions: activeSessions("secret", server.baseUrl),
        getHealthBaseUrl: () => server.baseUrl,
      });
      const lines: string[] = [];
      const error = await client
        .streamNdjson("/stream", { timeoutMs: 50, onLine: (line) => lines.push(line) })
        .catch((caught: unknown) => caught);
      expect(lines).toHaveLength(1);
      expect(error).toBeInstanceOf(RuntimeRequestTimeoutError);
    } finally {
      await server.close();
    }
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

function activeSessions(token: string, baseUrl = "http://127.0.0.1:8765"): RuntimeSessionRegistry {
  const sessions = new RuntimeSessionRegistry();
  sessions.set({
    ownership: "owned",
    connection: {
      baseUrl,
      sessionToken: token,
    },
  });
  return sessions;
}

async function startServer(
  handler: (response: ServerResponse) => void,
): Promise<{ readonly baseUrl: string; readonly close: () => Promise<void> }> {
  const server = createServer((_request, response) => handler(response));
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address() as AddressInfo;
  return {
    baseUrl: `http://127.0.0.1:${port}`,
    close: () =>
      new Promise<void>((resolve) => {
        server.closeAllConnections();
        server.close(() => resolve());
      }),
  };
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
