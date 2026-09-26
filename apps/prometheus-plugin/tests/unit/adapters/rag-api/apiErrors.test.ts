import { describe, expect, it } from "vitest";

import { mapRuntimeApiError } from "../../../../src/adapters/outbound/rag-api/apiErrors";

describe("mapRuntimeApiError", () => {
  it.each([
    ["UNAUTHORIZED", "reinitialize_runtime"],
    ["JOB_NOT_FOUND", "retry"],
    ["REVISION_CONFLICT", "retry"],
    ["VAULT_NOT_INDEXED", "reindex"],
    ["INDEX_CORRUPTED", "reindex"],
    ["INDEX_REBUILD_REQUIRED", "reindex"],
    ["RUNTIME_VERSION_INCOMPATIBLE", "update_plugin"],
    ["DOCUMENT_TOO_LARGE", "reduce_document"],
    ["QUERY_TOO_SHORT", "none"],
    ["VALIDATION_ERROR", "open_diagnostics"],
    ["OLLAMA_UNAVAILABLE", "restart_runtime"],
    ["LLM_MODEL_NOT_FOUND", "select_model"],
    ["LLM_TIMEOUT", "retry"],
    ["INTERNAL_ERROR", "open_diagnostics"],
  ] as const)("maps %s to recovery action %s", (code, action) => {
    const error = mapRuntimeApiError(
      { error: { code, message: "server detail", request_id: "request-a1" } },
      code === "UNAUTHORIZED" ? 401 : 409,
      null,
    );
    expect(error.runtimeCode).toBe(code);
    expect(error.recommendedAction).toBe(action);
    expect(error.requestId).toBe("request-a1");
    expect(error.message).not.toBe("server detail");
  });

  it("uses response header request id when the envelope is malformed", () => {
    const error = mapRuntimeApiError({ unexpected: true }, 500, "header-request");
    expect(error.code).toBe("RUNTIME_API_ERROR");
    expect(error.requestId).toBe("header-request");
    expect(error.recommendedAction).toBe("open_diagnostics");
  });
});
