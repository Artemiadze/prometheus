# Prometheus Runtime

Local Python runtime for parsing, indexing, retrieval, and grounded answers.

## Development

```bash
uv sync
make check
uv run prometheus-runtime --version
uv run prometheus-runtime serve --session-token "$PROMETHEUS_SESSION_TOKEN"
```

## Security and privacy (PRM-E12)

- **Session token (required):** pass `--session-token` or set `PROMETHEUS_SESSION_TOKEN`.
  Prefer the environment variable so the token does not appear in process listings.
  Protected routes expect `Authorization: Bearer <token>`; `/v1/health` stays open.
- **Host:** only `127.0.0.1:<port>`, `localhost:<port>`, and `[::1]:<port>` are accepted.
- **Origin / CORS:** browser Origins are limited to `app://obsidian.md`,
  `capacitor://localhost`, and loopback `http(s)://localhost|127.0.0.1|::1`.
  Foreign Origins and `Origin: null` receive `CROSS_ORIGIN_FORBIDDEN`.
- **Vault isolation:** each Vault gets its own SQLite + Qdrant directory; vector
  payloads are tagged with `vault_id` and cross-vault writes are rejected.
- **Offline guard:** in normal operation outbound sockets/DNS are limited to
  loopback. Set `PROMETHEUS_EMBEDDING_ALLOW_DOWNLOAD=true` only for first-run
  model download; the guard is skipped in that setup mode.
- **Local providers only:** `embedding_provider` is `fastembed`; `llm_host` must
  be an HTTP loopback Ollama URL.
