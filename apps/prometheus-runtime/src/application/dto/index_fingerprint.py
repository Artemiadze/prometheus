"""Full index compatibility fingerprint (Architecture.md, section 13)."""

from __future__ import annotations

from dataclasses import dataclass

from application.dto.embedding import EmbeddingFingerprint
from domain.errors import InvariantViolationError

#: Bumped whenever the Markdown parser changes how a Document is structured.
PARSER_SCHEMA_VERSION = 2

#: Bumped whenever the chunking algorithm changes chunk boundaries.
CHUNKER_ALGORITHM_VERSION = 2

#: Bumped whenever the Qdrant payload schema changes shape.
PAYLOAD_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class IndexFingerprint:
    """Every setting that must match between the active runtime and a stored index."""

    embedding: EmbeddingFingerprint
    parser_version: int
    chunker_version: int
    payload_schema_version: int
    chunk_size: int
    chunk_overlap: int

    def __post_init__(self) -> None:
        if (
            self.parser_version <= 0
            or self.chunker_version <= 0
            or self.payload_schema_version <= 0
            or self.chunk_size <= 0
            or self.chunk_overlap < 0
            or self.chunk_overlap >= self.chunk_size
        ):
            raise InvariantViolationError()
