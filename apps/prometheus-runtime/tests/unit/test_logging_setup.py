"""Tests for structured logging privacy and rotation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from prometheus_runtime.adapters.outbound.filesystem.data_dir import ensure_layout
from prometheus_runtime.adapters.outbound.filesystem.logging_setup import (
    configure_logging,
    log_context,
)


def _read_logs(log_directory: Path) -> str:
    return "".join(path.read_text(encoding="utf-8") for path in log_directory.glob("runtime.log*"))


def test_user_content_is_never_written(tmp_path: Path) -> None:
    layout = ensure_layout(tmp_path / "data")
    logger = configure_logging(layout)
    note = "private note text that must never be logged"

    logger.info(note, extra={"event": "document.indexed", "content": note})

    assert note not in _read_logs(layout.logs)


def test_json_contains_only_safe_required_fields(tmp_path: Path) -> None:
    layout = ensure_layout(tmp_path / "data")
    logger = configure_logging(layout)

    with log_context(request_id="request-123", vault_id="vault-456"):
        logger.info(
            "ignored",
            extra={
                "event": "search.completed",
                "duration_ms": 12.5,
                "result_count": 3,
                "query": "private query",
            },
        )

    record: dict[str, Any] = json.loads((layout.logs / "runtime.log").read_text(encoding="utf-8"))
    assert record == {
        "timestamp": record["timestamp"],
        "level": "INFO",
        "event": "search.completed",
        "request_id": "request-123",
        "vault_id": "vault-456",
        "duration_ms": 12.5,
        "result_count": 3,
    }


def test_rotation_caps_total_log_size(tmp_path: Path) -> None:
    layout = ensure_layout(tmp_path / "data")
    logger = configure_logging(layout, max_bytes=300, backup_count=2)

    for index in range(100):
        logger.info("private payload", extra={"event": "rotation.test", "result_count": index})

    files = list(layout.logs.glob("runtime.log*"))
    assert len(files) <= 3
    assert sum(path.stat().st_size for path in files) <= 900
    assert "private payload" not in _read_logs(layout.logs)
