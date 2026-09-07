"""Persistent compatibility metadata for one Vault's vector index."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from application.dto.embedding import EmbeddingFingerprint

PAYLOAD_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class IndexMetadata:
    """Index-relevant settings persisted independently from Qdrant points."""

    embedding: EmbeddingFingerprint
    payload_schema_version: int = PAYLOAD_SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "embedding": {
                "provider": self.embedding.provider,
                "model_id": self.embedding.model_id,
                "dimension": self.embedding.dimension,
            },
            "payload_schema_version": self.payload_schema_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IndexMetadata:
        embedding = data["embedding"]
        if not isinstance(embedding, dict):
            raise ValueError("embedding metadata must be an object")
        return cls(
            embedding=EmbeddingFingerprint(
                provider=str(embedding["provider"]),
                model_id=str(embedding["model_id"]),
                dimension=int(embedding["dimension"]),
            ),
            payload_schema_version=int(data["payload_schema_version"]),
        )


def read_index_metadata(path: Path) -> IndexMetadata | None:
    """Read metadata, returning None only when it has never been written."""

    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("index metadata must be an object")
    return IndexMetadata.from_dict(raw)


def write_index_metadata(path: Path, metadata: IndexMetadata) -> None:
    """Atomically persist metadata with user-only permissions."""

    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(metadata.to_dict(), sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    if os.name != "nt":
        temporary.chmod(0o600)
    temporary.replace(path)
