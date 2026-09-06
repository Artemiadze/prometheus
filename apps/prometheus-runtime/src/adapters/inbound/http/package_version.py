"""Installed distribution version for HTTP responses and OpenAPI metadata."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def package_version() -> str:
    """Return the installed prometheus-runtime version, with a dev fallback."""

    try:
        return version("prometheus-runtime")
    except PackageNotFoundError:  # pragma: no cover - editable/dev fallback
        return "0.1.0"
