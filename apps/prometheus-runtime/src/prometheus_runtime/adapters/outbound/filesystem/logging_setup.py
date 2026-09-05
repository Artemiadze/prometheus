"""Privacy-preserving structured logging."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Final

from prometheus_runtime.adapters.outbound.filesystem.data_dir import DataDirLayout

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
vault_id_context: ContextVar[str | None] = ContextVar("vault_id", default=None)

_IDENTIFIER: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_EVENT: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_SENSITIVE_FIELDS: Final[frozenset[str]] = frozenset(
    {"answer", "content", "message", "prompt", "query", "text"}
)
_NUMERIC_METRICS: Final[frozenset[str]] = frozenset(
    {"chunk_count", "document_count", "result_count", "token_count"}
)


def _safe_identifier(value: object) -> str | None:
    if isinstance(value, str) and _IDENTIFIER.fullmatch(value):
        return value
    return None


class RedactionFilter(logging.Filter):
    """Remove user-content fields before any handler can process the record."""

    def filter(self, record: logging.LogRecord) -> bool:
        for field in _SENSITIVE_FIELDS:
            if hasattr(record, field):
                setattr(record, field, "[REDACTED]")
        record.msg = "[REDACTED]"
        record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    """Serialize an allowlist of identifiers and numeric metrics as one JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        raw_event = getattr(record, "event", None)
        event = raw_event if isinstance(raw_event, str) and _EVENT.fullmatch(raw_event) else "log"
        payload: dict[str, str | int | float | None] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "event": event,
            "request_id": _safe_identifier(
                getattr(record, "request_id", None) or request_id_context.get()
            ),
            "vault_id": _safe_identifier(
                getattr(record, "vault_id", None) or vault_id_context.get()
            ),
            "duration_ms": None,
        }

        duration = getattr(record, "duration_ms", None)
        if isinstance(duration, (int, float)) and not isinstance(duration, bool):
            payload["duration_ms"] = duration

        for name in _NUMERIC_METRICS:
            value = getattr(record, name, None)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                payload[name] = value
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


@contextmanager
def log_context(*, request_id: str | None = None, vault_id: str | None = None) -> Iterator[None]:
    """Bind correlation identifiers for logs emitted in the current context."""

    request_token = request_id_context.set(request_id)
    vault_token = vault_id_context.set(vault_id)
    try:
        yield
    finally:
        request_id_context.reset(request_token)
        vault_id_context.reset(vault_token)


def configure_logging(
    layout: DataDirLayout,
    level: str = "INFO",
    *,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Logger:
    """Configure and return the isolated runtime logger."""

    log_path: Path = layout.logs / "runtime.log"
    handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.addFilter(RedactionFilter())
    handler.setFormatter(JsonFormatter())

    logger = logging.getLogger("prometheus_runtime")
    for previous in logger.handlers:
        previous.close()
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger
