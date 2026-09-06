"""Prometheus local RAG runtime bootstrap."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("prometheus-runtime")
except PackageNotFoundError:  # pragma: no cover - editable/dev fallback
    __version__ = "0.1.0"
