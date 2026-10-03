"""JSON report helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, cast

REPORT_SCHEMA_VERSION = 1


def fingerprint_to_dict(fingerprint: object) -> dict[str, Any]:
    if is_dataclass(fingerprint):
        payload = asdict(cast(Any, fingerprint))
        embedding = payload.get("embedding")
        if is_dataclass(embedding):
            payload["embedding"] = asdict(cast(Any, embedding))
        return payload
    raise TypeError("expected dataclass fingerprint")


def write_json_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
