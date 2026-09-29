"""Browser-origin and Host-header protection for the localhost API."""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import Request

from domain.errors import PrometheusError

ALLOWED_EXACT_ORIGINS: frozenset[str] = frozenset(
    {
        "app://obsidian.md",
        "capacitor://localhost",
    }
)
_LOOPBACK_ORIGIN_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1", "[::1]"})
CORS_ALLOW_METHODS = "GET, POST, PUT, DELETE, OPTIONS"
CORS_ALLOW_HEADERS = "Authorization, Content-Type, X-Request-ID, X-Prometheus-Plugin-Version"
CORS_EXPOSE_HEADERS = "X-Request-ID"


class CrossOriginForbiddenError(PrometheusError):
    """Raised when a browser origin tries to access the local runtime."""

    code = "CROSS_ORIGIN_FORBIDDEN"
    default_message = "Cross-origin requests are not allowed"


class UntrustedHostError(PrometheusError):
    """Raised when the request Host does not address the local runtime."""

    code = "UNTRUSTED_HOST"
    default_message = "Request Host is not allowed"


def is_allowed_origin(origin: str) -> bool:
    """Return whether a browser Origin may call the localhost API."""

    if origin in ALLOWED_EXACT_ORIGINS:
        return True
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        return False
    host = (parsed.hostname or "").casefold()
    return host in {item.casefold() for item in _LOOPBACK_ORIGIN_HOSTS}


def require_allowed_origin(request: Request) -> None:
    """Reject disallowed browser origins; allow non-browser clients with no Origin."""

    origin = request.headers.get("origin")
    if origin is None:
        return
    if origin.casefold() == "null" or not is_allowed_origin(origin):
        raise CrossOriginForbiddenError()


def require_trusted_host(request: Request) -> None:
    """Accept only the configured loopback endpoint."""

    container = getattr(request.app.state, "container", None)
    settings = getattr(container, "settings", None)
    if settings is None:
        return

    port = settings.port
    trusted_hosts = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
    host = request.headers.get("host", "").casefold()
    if host not in {item.casefold() for item in trusted_hosts}:
        raise UntrustedHostError()


def cors_headers_for(origin: str) -> dict[str, str]:
    """Build Access-Control headers for an already-validated Origin."""

    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": CORS_ALLOW_METHODS,
        "Access-Control-Allow-Headers": CORS_ALLOW_HEADERS,
        "Access-Control-Expose-Headers": CORS_EXPOSE_HEADERS,
        "Access-Control-Max-Age": "600",
        "Vary": "Origin",
    }
