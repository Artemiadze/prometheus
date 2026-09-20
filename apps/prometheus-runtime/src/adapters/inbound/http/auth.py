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
    """Validate bearer credentials when the runtime was started with a token."""

    token_setting = request.app.state.container.settings.session_token
    if token_setting is None:
        return
    raw_header = request.headers.get("Authorization", "")
    provided = raw_header.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(provided, token_setting.get_secret_value()):
        raise UnauthorizedError()
