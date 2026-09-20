"""Browser-origin and Host-header protection for the localhost API."""

from __future__ import annotations

from fastapi import Request

from domain.errors import PrometheusError


class CrossOriginForbiddenError(PrometheusError):
    """Raised when a browser origin tries to access the local runtime."""

    code = "CROSS_ORIGIN_FORBIDDEN"
    default_message = "Cross-origin requests are not allowed"


class UntrustedHostError(PrometheusError):
    """Raised when the request Host does not address the local runtime."""

    code = "UNTRUSTED_HOST"
    default_message = "Request Host is not allowed"


def reject_cross_origin(request: Request) -> None:
    """Reject every browser-originated request; this API has no CORS surface."""

    if "origin" in request.headers:
        raise CrossOriginForbiddenError()


def require_trusted_host(request: Request) -> None:
    """Accept only the configured loopback endpoint."""

    container = request.app.state.container
    settings = getattr(container, "settings", None)
    if settings is None:
        return

    port = settings.port
    trusted_hosts = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
    if request.headers.get("host", "").casefold() not in trusted_hosts:
        raise UntrustedHostError()
