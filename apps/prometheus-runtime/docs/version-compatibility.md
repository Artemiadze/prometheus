# Plugin and runtime version compatibility

Prometheus Runtime accepts Obsidian plugin versions in the range **`>=0.1.0,<0.2.0`**.

## Negotiation

| Item | Value |
|---|---|
| Request header | `X-Prometheus-Plugin-Version` |
| Format | Strict semver `MAJOR.MINOR.PATCH` |
| Compatible range | `>=0.1.0,<0.2.0` |
| Exempt endpoint | `GET /v1/health` (spawn readiness) |

Protected API routes require the header. Missing, malformed, or out-of-range values return:

```json
{
  "error": {
    "code": "RUNTIME_VERSION_INCOMPATIBLE",
    "message": "...",
    "request_id": "..."
  }
}
```

HTTP status: **409**.

The runtime package version is exported independently via `GET /v1/health` (`version`),
`GET /v1/status` (`runtime_version` / `api_version`), and `prometheus-runtime --version`.
