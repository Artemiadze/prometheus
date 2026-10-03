"""Chunk identifier value object."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass

from domain.errors import InvalidIdentifierError
from domain.value_objects.document_id import DocumentId

_CHUNK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{5,127}$")


@dataclass(frozen=True, slots=True)
class ChunkId:
    """A stable chunk identifier independent of infrastructure storage."""

    value: str

    def __post_init__(self) -> None:
        if not _CHUNK_ID.fullmatch(self.value):
            raise InvalidIdentifierError()

    @classmethod
    def from_parts(
        cls,
        document_id: DocumentId,
        heading_path: Sequence[str],
        section_ordinal: int,
        chunk_index: int,
    ) -> ChunkId:
        if section_ordinal < 0 or chunk_index < 0:
            raise InvalidIdentifierError()
        identity = json.dumps(
            [document_id.value, *heading_path, section_ordinal, chunk_index],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return cls(hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32])

    def __str__(self) -> str:
        return self.value
