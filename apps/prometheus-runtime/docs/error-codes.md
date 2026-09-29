# HTTP error codes

| Code | HTTP status | Meaning |
|---|---:|---|
| `UNAUTHORIZED` | 401 | A protected endpoint received no valid session token. |
| `CROSS_ORIGIN_FORBIDDEN` | 403 | The browser Origin is outside the local Obsidian allowlist. |
| `UNTRUSTED_HOST` | 400 | The Host header does not address the configured loopback port. |
| `JOB_NOT_FOUND` | 404 | The requested background job does not exist. |
| `REVISION_CONFLICT` | 409 | A document revision is older than its indexed revision. |
| `VAULT_NOT_INDEXED` | 409 | The Vault has no usable index. |
| `VAULT_MISMATCH` | 409 | A document or vector write targeted a different Vault than the scoped runtime. |
| `INDEX_CORRUPTED` | 409 | The vector index must be rebuilt. |
| `INDEX_REBUILD_REQUIRED` | 409 | The active index fingerprint is incompatible. |
| `RUNTIME_VERSION_INCOMPATIBLE` | 409 | The Obsidian plugin version is outside the supported range. |
| `DOCUMENT_TOO_LARGE` | 422 | The document exceeds configured indexing size or chunk limits. |
| `QUERY_TOO_SHORT` | 422 | The search or chat query is too short. |
| `VALIDATION_ERROR` | 422 | The JSON request body does not conform to the API schema. |
| `OLLAMA_UNAVAILABLE` | 503 | The local Ollama process cannot be reached. |
| `LLM_MODEL_NOT_FOUND` | 503 | The selected local model is not installed. |
| `LLM_TIMEOUT` | 504 | Local model generation exceeded its timeout. |
| `INTERNAL_ERROR` | 500 | An unexpected internal failure occurred. |

### Background job error codes

These values may appear in the `error` field of a failed job (`GET /v1/jobs/{jobId}`), not in the HTTP error envelope:

| Code | Meaning |
|---|---|
| `JOB_INTERRUPTED` | The process stopped before the job finished. |
| `JOB_FAILED` | A background sync job failed unexpectedly. |
| `REINDEX_FAILED` | A background reindex job failed unexpectedly. |

All error responses use the versioned envelope:

```json
{
  "error": {
    "code": "QUERY_TOO_SHORT",
    "message": "Search query is too short",
    "request_id": "..."
  }
}
```
