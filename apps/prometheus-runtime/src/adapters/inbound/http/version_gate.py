"""Plugin version negotiation for the localhost API."""

from __future__ import annotations

from fastapi import Request

from application.errors import RuntimeVersionIncompatibleError
from application.services.version_compatibility import (
    COMPATIBLE_PLUGIN_RANGE,
    is_plugin_compatible,
)

PLUGIN_VERSION_HEADER = "X-Prometheus-Plugin-Version"


def require_compatible_plugin_version(request: Request) -> None:
    """Reject protected requests from an unsupported plugin version."""

    provided = request.headers.get(PLUGIN_VERSION_HEADER, "").strip()
    if not provided or not is_plugin_compatible(provided):
        # Do not echo the client-supplied header value back into the envelope.
        raise RuntimeVersionIncompatibleError(
            f"Plugin version is outside the compatible range {COMPATIBLE_PLUGIN_RANGE}"
        )
