import { describe, expect, it } from "vitest";

import { HttpRagGateway } from "../../../../src/adapters/outbound/rag-api/HttpRagGateway";
import { RuntimeHttpClient } from "../../../../src/adapters/outbound/rag-api/RuntimeHttpClient";
import { RuntimeSessionRegistry } from "../../../../src/application/services/RuntimeSessionRegistry";
import {
  RuntimeApiError,
  RuntimeContractError,
  RuntimeVersionIncompatibleError,
} from "../../../../src/domain/errors";
import { DocumentId } from "../../../../src/domain/value-objects/DocumentId";
import { NotePath } from "../../../../src/domain/value-objects/NotePath";
import { SearchScope } from "../../../../src/domain/value-objects/SearchScope";
import { VaultId } from "../../../../src/domain/value-objects/VaultId";

type FetchCall = {
  readonly url: string;
  readonly method: string;
  readonly body: unknown;
};

describe("HttpRagGateway", () => {
  it("maps health, vault status and local models", async () => {
    const harness = createHarness([
      { status: "ok", version: "0.1.5" },
      {
        runtime_version: "0.1.5",
        api_version: "0.1.5",
        index_state: "ready",
        llm_available: true,
        llm_model: "qwen3:4b",
        document_count: 3,
        chunk_count: 9,
        last_indexed_at: "2026-09-26T08:00:00.000Z",
        index_size_bytes: 42,
        reindex_required: false,
        reindex_reason: null,
      },
      {
        models: [{ name: "qwen3:4b", size_bytes: 10, quantization: "Q4" }],
      },
    ]);

    expect(await harness.gateway.health()).toEqual({ status: "ok", version: "0.1.5" });
    const status = await harness.gateway.status(VaultId.create("vault-a1"));
    expect(status).toMatchObject({
      runtimeVersion: "0.1.5",
      documentCount: 3,
      indexSizeBytes: 42,
    });
    expect(status.lastIndexedAt?.toISOString()).toBe("2026-09-26T08:00:00.000Z");
    expect(await harness.gateway.listModels()).toEqual([
      { name: "qwen3:4b", sizeBytes: 10, quantization: "Q4" },
    ]);
    expect(harness.calls[1]?.url).toContain("/v1/status?vaultId=vault-a1");
  });

  it("serializes stable document identities, sync and reindex", async () => {
    const harness = createHarness([
      { status: "ok", version: "0.1.0" },
      {
        document_id: "document-a1",
        skipped: true,
        relocated: false,
        created_chunks: 0,
        deleted_chunks: 0,
      },
      { document_id: "document-a1", removed: true, removed_chunks: 2 },
      { job_id: "job-sync", status_url: "/v1/jobs/job-sync" },
      { job_id: "job-reindex", status_url: "/v1/jobs/job-reindex" },
    ]);
    const vaultId = VaultId.create("vault-a1");
    const path = NotePath.create("notes/a.md");
    const documentId = DocumentId.fromNotePath(path);
    const input = {
      path,
      content: "body",
      revision: 2,
      modifiedAt: new Date("2026-09-26T08:00:00.000Z"),
    };

    const result = await harness.gateway.upsertDocument(vaultId, documentId, input);
    expect(result.skipped).toBe(true);
    await harness.gateway.deleteDocument(vaultId, documentId);
    expect(
      await harness.gateway.syncComplete(vaultId, [
        {
          documentId,
          path,
          contentHash: "hash",
          revision: 2,
          modifiedAt: input.modifiedAt,
        },
      ]),
    ).toMatchObject({ jobId: "job-sync", status: "pending", progress: 0 });
    expect(await harness.gateway.reindex(vaultId, [{ documentId, ...input }])).toMatchObject({
      jobId: "job-reindex",
      status: "pending",
    });

    expect(harness.calls[1]?.method).toBe("PUT");
    expect(harness.calls[1]?.url).toContain(`/vaults/vault-a1/documents/${documentId.value}`);
    expect(harness.calls[1]?.body).toEqual({
      path: "notes/a.md",
      content: "body",
      revision: 2,
      modified_at: "2026-09-26T08:00:00.000Z",
    });
    expect(harness.calls[4]?.body).toMatchObject({
      documents: [
        {
          document_id: documentId.value,
          path: "notes/a.md",
          revision: 2,
        },
      ],
    });
  });

  it("repeats idempotent upsert with the same identity and honors skipped", async () => {
    const path = NotePath.create("notes/stable.md");
    const documentId = DocumentId.fromNotePath(path);
    const success = {
      document_id: documentId.value,
      relocated: false,
      created_chunks: 1,
      deleted_chunks: 0,
    };
    const harness = createHarness([
      { status: "ok", version: "0.1.0" },
      { ...success, skipped: false },
      { ...success, skipped: true, created_chunks: 0 },
    ]);
    const input = {
      path,
      content: "same body",
      revision: 1,
      modifiedAt: new Date("2026-09-26T08:00:00.000Z"),
    };
    const vaultId = VaultId.create("vault-a1");

    expect((await harness.gateway.upsertDocument(vaultId, documentId, input)).skipped).toBe(false);
    expect((await harness.gateway.upsertDocument(vaultId, documentId, input)).skipped).toBe(true);
    expect(harness.calls[1]?.url).toBe(harness.calls[2]?.url);
    expect(harness.calls[1]?.body).toEqual(harness.calls[2]?.body);
  });

  it("does not retry a revision conflict", async () => {
    const conflict = new Response(
      JSON.stringify({
        error: {
          code: "REVISION_CONFLICT",
          message: "stale revision",
          request_id: "conflict-request",
        },
      }),
      { status: 409, headers: { "Content-Type": "application/json" } },
    );
    const harness = createHarness([{ status: "ok", version: "0.1.0" }, conflict]);
    const path = NotePath.create("notes/a.md");
    const result = harness.gateway
      .upsertDocument(VaultId.create("vault-a1"), DocumentId.fromNotePath(path), {
        path,
        content: "stale",
        revision: 1,
        modifiedAt: new Date(0),
      })
      .catch((error: unknown) => error);
    const error = await result;
    expect(error).toBeInstanceOf(RuntimeApiError);
    expect(error).toMatchObject({ code: "REVISION_CONFLICT" });
    expect(harness.calls).toHaveLength(2);
  });

  it("maps search hits and grounded chat sources", async () => {
    const harness = createHarness([
      { status: "ok", version: "0.1.0" },
      {
        results: [
          {
            path: "notes/a.md",
            heading: "Section",
            text: "matching text",
            score: 0.9,
          },
        ],
      },
      {
        answer: "Grounded answer",
        sources: [{ path: "notes/a.md", heading: "Section" }],
        insufficient_context: false,
      },
    ]);
    const vaultId = VaultId.create("vault-a1");
    const scope = SearchScope.currentFolder("notes");

    const hits = await harness.gateway.search(vaultId, "query", scope, 5);
    expect(hits[0]?.path.value).toBe("notes/a.md");
    const answer = await harness.gateway.chat(vaultId, "question", scope);
    expect(answer.sources[0]?.notePath.value).toBe("notes/a.md");
    expect(answer.sources[0]?.heading).toBe("Section");
    expect(harness.calls[1]?.body).toEqual({
      query: "query",
      limit: 5,
      scope: { mode: "current_folder", note: null, folders: ["notes"] },
    });
  });

  it("maps job status and cancellation", async () => {
    const harness = createHarness([
      { status: "ok", version: "0.1.0" },
      {
        job_id: "job-a1",
        status: "running",
        progress: 0.5,
        error: null,
      },
      null,
    ]);
    expect(await harness.gateway.getJob("job-a1")).toEqual({
      jobId: "job-a1",
      status: "running",
      progress: 0.5,
      error: null,
    });
    await harness.gateway.cancelJob("job-a1");
    expect(harness.calls[2]?.method).toBe("DELETE");
  });

  it("rechecks runtime compatibility when session credentials rotate", async () => {
    const harness = createHarness([
      { status: "ok", version: "0.1.0" },
      { models: [] },
      { status: "ok", version: "0.1.1" },
      { models: [] },
    ]);
    await harness.gateway.listModels();
    harness.sessions.set({
      ownership: "owned",
      connection: {
        baseUrl: "http://127.0.0.1:8765",
        sessionToken: "rotated-secret",
      },
    });
    await harness.gateway.listModels();
    expect(harness.calls.map((call) => new URL(call.url).pathname)).toEqual([
      "/v1/health",
      "/v1/models",
      "/v1/health",
      "/v1/models",
    ]);
  });

  it("rejects incompatible runtime and malformed domain paths", async () => {
    const incompatible = createHarness([{ status: "ok", version: "0.2.0" }, { models: [] }]);
    await expect(incompatible.gateway.listModels()).rejects.toBeInstanceOf(
      RuntimeVersionIncompatibleError,
    );
    expect(incompatible.calls).toHaveLength(1);

    const malformed = createHarness([
      { status: "ok", version: "0.1.0" },
      {
        results: [{ path: "../escape.md", heading: null, text: "x", score: 1 }],
      },
    ]);
    await expect(
      malformed.gateway.search(VaultId.create("vault-a1"), "query", SearchScope.entireVault(), 10),
    ).rejects.toBeInstanceOf(RuntimeContractError);
  });
});

function createHarness(responses: readonly unknown[]): {
  readonly gateway: HttpRagGateway;
  readonly calls: FetchCall[];
  readonly sessions: RuntimeSessionRegistry;
} {
  const queue = [...responses];
  const calls: FetchCall[] = [];
  const fetchFn: typeof fetch = async (input, init = {}) => {
    if (typeof input !== "string") {
      throw new Error("Expected string URL");
    }
    const body = typeof init.body === "string" ? (JSON.parse(init.body) as unknown) : null;
    calls.push({
      url: input,
      method: init.method ?? "GET",
      body,
    });
    if (queue.length === 0) {
      throw new Error("No queued response");
    }
    const next = queue.shift();
    return next instanceof Response ? next : jsonResponse(next);
  };
  const sessions = new RuntimeSessionRegistry();
  sessions.set({
    ownership: "owned",
    connection: {
      baseUrl: "http://127.0.0.1:8765",
      sessionToken: "secret",
    },
  });
  const http = new RuntimeHttpClient({
    sessions,
    getHealthBaseUrl: () => "http://127.0.0.1:8765",
    fetchFn,
    requestIdFactory: () => "request-id",
  });
  return { gateway: new HttpRagGateway(http), calls, sessions };
}

function jsonResponse(payload: unknown): Response {
  if (payload === null) {
    return new Response(null, { status: 202 });
  }
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}
