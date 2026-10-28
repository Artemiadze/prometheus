"""Reuse previously computed embeddings by chunk content hash."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from application.dto.chunk_fingerprint import ChunkFingerprint
from application.ports.vector_index import VectorIndex
from domain.entities.chunk import Chunk
from domain.value_objects.chunk_id import ChunkId


@dataclass(frozen=True, slots=True)
class ResolvedEmbeddings:
    """Partial vectors for a document; ``None`` slots still need embedding."""

    vectors: tuple[Sequence[float] | None, ...]
    missing_chunks: tuple[Chunk, ...]
    missing_positions: tuple[int, ...]

    @property
    def complete(self) -> bool:
        return not self.missing_chunks


def resolve_reusable_embeddings(
    chunks: Sequence[Chunk],
    fingerprints: Sequence[ChunkFingerprint],
    vector_source: VectorIndex,
) -> ResolvedEmbeddings:
    """Match new chunks to prior vectors by ``content_hash``, ignoring chunk index shifts."""

    by_hash: dict[str, deque[ChunkId]] = defaultdict(deque)
    for fingerprint in fingerprints:
        by_hash[fingerprint.content_hash].append(fingerprint.chunk_id)

    reuse_ids: list[ChunkId] = []
    assigned: list[ChunkId | None] = [None] * len(chunks)
    for index, chunk in enumerate(chunks):
        bucket = by_hash.get(chunk.content_hash)
        if bucket:
            chunk_id = bucket.popleft()
            assigned[index] = chunk_id
            reuse_ids.append(chunk_id)

    cached: Mapping[str, Sequence[float]] = (
        vector_source.retrieve_vectors(reuse_ids) if reuse_ids else {}
    )

    vectors: list[Sequence[float] | None] = [None] * len(chunks)
    missing_chunks: list[Chunk] = []
    missing_positions: list[int] = []
    for index, chunk in enumerate(chunks):
        reused_id = assigned[index]
        if reused_id is not None and reused_id.value in cached:
            vectors[index] = cached[reused_id.value]
            continue
        missing_chunks.append(chunk)
        missing_positions.append(index)
    return ResolvedEmbeddings(
        vectors=tuple(vectors),
        missing_chunks=tuple(missing_chunks),
        missing_positions=tuple(missing_positions),
    )


def fill_resolved_embeddings(
    resolved: ResolvedEmbeddings,
    embedded: Sequence[Sequence[float]],
) -> tuple[Sequence[float], ...]:
    """Merge freshly embedded vectors into a resolved partial result."""

    if len(embedded) != len(resolved.missing_positions):
        raise ValueError("embedded vector count must match missing positions")
    vectors: list[Sequence[float] | None] = list(resolved.vectors)
    for position, vector in zip(resolved.missing_positions, embedded, strict=True):
        vectors[position] = vector
    filled: list[Sequence[float]] = []
    for slot in vectors:
        if slot is None:
            raise ValueError("unresolved embedding slot")
        filled.append(slot)
    return tuple(filled)
