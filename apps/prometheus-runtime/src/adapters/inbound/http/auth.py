"""Session-token protection for localhost API routes."""

from __future__ import annotations

import secrets

from fastapi import Request

from domain.errors import PrometheusError


class UnauthorizedError(PrometheusError):
    """Raised when a protected route has no valid spawned session token."""

    code = "UNAUTHORIZED"
    default_message = "A valid session token is required"


def require_session_token(request: Request) -> None:
    """Validate bearer credentials; fail closed when no token is configured."""

    container = getattr(request.app.state, "container", None)
    settings = getattr(container, "settings", None)
    token_setting = getattr(settings, "session_token", None)
    if token_setting is None:
        raise UnauthorizedError()

    provided = _bearer_token(request.headers.get("Authorization"))
    if provided is None:
        raise UnauthorizedError()

    expected = token_setting.get_secret_value()
    try:
        provided_bytes = provided.encode("utf-8")
        expected_bytes = expected.encode("utf-8")
    except (AttributeError, UnicodeError):
        raise UnauthorizedError() from None

    if not secrets.compare_digest(provided_bytes, expected_bytes):
        raise UnauthorizedError()


def _bearer_token(raw_header: str | None) -> str | None:
    """Extract the token from a ``Bearer`` Authorization header."""

    if raw_header is None:
        return None
    scheme, _, remainder = raw_header.partition(" ")
    if scheme.casefold() != "bearer" or not remainder or remainder != remainder.strip():
        return None
    token = remainder.strip()
    return token if token else None
