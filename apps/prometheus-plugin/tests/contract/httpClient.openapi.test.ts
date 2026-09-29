import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { mapRuntimeApiError } from "../../src/adapters/outbound/rag-api/apiErrors";
import { HttpRagGateway } from "../../src/adapters/outbound/rag-api/HttpRagGateway";
import { RuntimeHttpClient } from "../../src/adapters/outbound/rag-api/RuntimeHttpClient";
import { RuntimeSessionRegistry } from "../../src/application/services/RuntimeSessionRegistry";
import { RuntimeApiError } from "../../src/domain/errors";
import { NotePath } from "../../src/domain/value-objects/NotePath";
import { VaultId } from "../../src/domain/value-objects/VaultId";

/**
 * PLG-83 — Contract-oriented HTTP client tests against OpenAPI ErrorEnvelope shape.
 * A fake runtime returns bodies that must satisfy contracts/openapi.yaml ErrorEnvelope.
 */

const OPENAPI_PATH = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../../contracts/openapi.yaml",
);

function loadOpenApi(): string {
  return readFileSync(OPENAPI_PATH, "utf8");
}

function assertErrorEnvelope(body: unknown): asserts body is {
  error: { code: string; message: string; request_id: string };
} {
  if (typeof body !== "object" || body === null) {
    throw new Error("ErrorEnvelope must be an object");
  }
  const record = body as Record<string, unknown>;
  if (Object.keys(record).length !== 1 || !("error" in record)) {
    throw new Error("ErrorEnvelope must contain only error");
  }
  const error = record["error"];
  if (typeof error !== "object" || error === null) {
    throw new Error("ErrorEnvelope.error must be an object");
  }
  const fields = error as Record<string, unknown>;
  for (const key of ["code", "message", "request_id"] as const) {
    if (typeof fields[key] !== "string") {
      throw new Error(`ErrorEnvelope.error.${key} must be a string`);
    }
  }
  if (Object.keys(fields).sort().join(",") !== "code,message,request_id") {
    throw new Error("ErrorEnvelope.error has unexpected fields");
  }
}

function envelope(code: string, status: number, requestId: string): Response {
  const body = {
    error: {
      code,
      message: `server detail for ${code}`,
      request_id: requestId,
    },
  };
  assertErrorEnvelope(body);
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "X-Request-ID": requestId },
  });
}

describe("HTTP client OpenAPI contracts (PLG-83)", () => {
  it("keeps ErrorEnvelope schema present in openapi.yaml", () => {
    const spec = loadOpenApi();
    expect(spec).toContain("ErrorEnvelope");
    expect(spec).toContain('"title": "ErrorEnvelope"');
    expect(spec).toMatch(/"required":\s*\[\s*"error"\s*]/);
    expect(spec).toMatch(/"required":\s*\[[^\]]*"code"[^\]]*"message"[^\]]*"request_id"/s);
  });

  it("maps 401 UNAUTHORIZED from a contract-shaped envelope", async () => {
    const sessions = new RuntimeSessionRegistry();
    sessions.set({
      connection: { baseUrl: "http://127.0.0.1:8765", sessionToken: "secret" },
      ownership: "owned",
    });
    const client = new RuntimeHttpClient({
      sessions,
      getHealthBaseUrl: () => "http://127.0.0.1:8765",
      fetchFn: async () => envelope("UNAUTHORIZED", 401, "req-401"),
      onUnauthorized: () => {
        sessions.clear();
      },
    });
    const error = await client
      .request("/models", { decode: () => true })
      .catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(RuntimeApiError);
    expect(error).toMatchObject({
      code: "UNAUTHORIZED",
      requestId: "req-401",
      recommendedAction: "reinitialize_runtime",
    });
    expect(sessions.get()).toBeNull();
  });

  it("maps 404 JOB_NOT_FOUND from a contract-shaped envelope", async () => {
    const sessions = new RuntimeSessionRegistry();
    sessions.set({
      connection: { baseUrl: "http://127.0.0.1:8765", sessionToken: "secret" },
      ownership: "owned",
    });
    const client = new RuntimeHttpClient({
      sessions,
      getHealthBaseUrl: () => "http://127.0.0.1:8765",
      fetchFn: async () => envelope("JOB_NOT_FOUND", 404, "req-404"),
    });
    const error = await client
      .request("/jobs/missing", { decode: () => true })
      .catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(RuntimeApiError);
    expect(error).toMatchObject({
      code: "JOB_NOT_FOUND",
      requestId: "req-404",
      recommendedAction: "retry",
    });
  });

  it("maps 409 REVISION_CONFLICT without retrying via HttpRagGateway", async () => {
    const sessions = new RuntimeSessionRegistry();
    sessions.set({
      connection: { baseUrl: "http://127.0.0.1:8765", sessionToken: "secret" },
      ownership: "owned",
    });
    let calls = 0;
    const fetchFn = async (): Promise<Response> => {
      calls += 1;
      if (calls === 1) {
        return new Response(JSON.stringify({ status: "ok", version: "0.1.0" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return envelope("REVISION_CONFLICT", 409, "req-409");
    };
    const gateway = new HttpRagGateway(
      new RuntimeHttpClient({
        sessions,
        getHealthBaseUrl: () => "http://127.0.0.1:8765",
        fetchFn,
      }),
    );
    const path = NotePath.create("notes/a.md");
    const { DocumentId } = await import("../../src/domain/value-objects/DocumentId");
    const error = await gateway
      .upsertDocument(VaultId.create("vault-a1"), DocumentId.fromNotePath(path), {
        path,
        content: "body",
        revision: 1,
        modifiedAt: new Date(0),
      })
      .catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(RuntimeApiError);
    expect(error).toMatchObject({ code: "REVISION_CONFLICT", requestId: "req-409" });
    expect(calls).toBe(2);
  });

  it("rejects a body that diverges from ErrorEnvelope required fields", () => {
    const mapped = mapRuntimeApiError({ not_an_error: true }, 500, "header-id");
    expect(mapped.code).toBe("RUNTIME_API_ERROR");
    expect(mapped.requestId).toBe("header-id");

    expect(() => assertErrorEnvelope({ error: { code: "UNAUTHORIZED", message: "x" } })).toThrow();
  });
});
