# Plugin and runtime version compatibility

Public **0.1** version freeze: see [`docs/release/0.1.md`](../../../docs/release/0.1.md).

Prometheus Runtime accepts Obsidian plugin versions in the range **`>=0.1.0,<0.2.0`**.

## Negotiation

| Item | Value |
|---|---|
| Request header | `X-Prometheus-Plugin-Version` |
| Format | Strict semver `MAJOR.MINOR.PATCH` (no prerelease or build metadata) |
| Compatible range | `>=0.1.0,<0.2.0` |
| API contract version | `0.1.0` (independent of the installed package version) |
| Exempt endpoint | `GET /v1/health` (spawn readiness) |

Protected API routes require the header. Missing, malformed, prerelease, or out-of-range
values return:

```json
{
  "error": {
    "code": "RUNTIME_VERSION_INCOMPATIBLE",
    "message": "Plugin version is outside the compatible range >=0.1.0,<0.2.0",
    "request_id": "..."
  }
}
```

HTTP status: **409**. The error message never echoes the client-supplied header value.

## Version surfaces

| Surface | Field | Meaning |
|---|---|---|
| `GET /v1/health` | `version` | Installed runtime package version |
| `GET /v1/status` | `runtime_version` | Installed runtime package version |
| `GET /v1/status` | `api_version` | Stable HTTP API contract version (`0.1.0`) |
| `prometheus-runtime --version` | stdout | Installed runtime package version |

When the package release advances (for example `0.1.1`), `api_version` stays `0.1.0`
until a breaking localhost contract change bumps it deliberately.
