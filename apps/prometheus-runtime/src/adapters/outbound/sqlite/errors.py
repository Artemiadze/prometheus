"""Safe failures exposed by the SQLite metadata adapter."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from functools import wraps

from domain.errors import PrometheusError


class SchemaDowngradeError(PrometheusError):
    """Raised when the on-disk schema is newer than this runtime supports."""

    code = "SCHEMA_DOWNGRADE_UNSUPPORTED"
    default_message = "Metadata database schema is newer than this runtime supports"

    def __init__(self, stored_version: int, supported_version: int) -> None:
        self.stored_version = stored_version
        self.supported_version = supported_version
        super().__init__()


class MetadataStoreError(PrometheusError):
    """Raised when a low-level SQLite failure must not leak past the adapter."""

    code = "METADATA_STORE_FAILED"
    default_message = "Metadata store operation failed"


class LexicalIndexUnavailableError(PrometheusError):
    """Raised when SQLite was built without FTS5 support."""

    code = "LEXICAL_INDEX_UNAVAILABLE"
    default_message = "Lexical search requires SQLite FTS5 support"


class VectorExtensionUnavailableError(PrometheusError):
    """Raised when the sqlite-vec extension cannot be loaded."""

    code = "VECTOR_EXTENSION_UNAVAILABLE"
    default_message = "Dense vector search requires the sqlite-vec SQLite extension"


def wrap_driver_errors[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Translate ``sqlite3.Error`` into the stable :class:`MetadataStoreError`."""

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)
        except sqlite3.Error as error:
            raise MetadataStoreError() from error

    return wrapper
