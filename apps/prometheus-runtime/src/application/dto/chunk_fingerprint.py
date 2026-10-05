"""Indexed chunk identity for incremental re-embedding."""

from dataclasses import dataclass

from domain.value_objects.chunk_id import ChunkId


@dataclass(frozen=True, slots=True)
class ChunkFingerprint:
    chunk_id: ChunkId
    chunk_index: int
    content_hash: str
