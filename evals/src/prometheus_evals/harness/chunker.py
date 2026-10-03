"""Chunker wrapper that keeps chunk_index unique across all sections."""

from __future__ import annotations

from collections.abc import Sequence

from application.dto.parsed_document import ParsedDocument
from application.ports.chunker import Chunker
from domain.entities.chunk import Chunk
from domain.entities.document import compute_content_hash
from domain.value_objects.chunk_id import ChunkId


class EvalChunker(Chunker):
    """Assign monotonic chunk_index values across an entire parsed document."""

    def __init__(self, inner: Chunker) -> None:
        self._inner = inner

    def chunk(self, parsed_document: ParsedDocument) -> Sequence[Chunk]:
        raw = tuple(self._inner.chunk(parsed_document))
        if not raw:
            return raw
        reindexed: list[Chunk] = []
        for index, chunk in enumerate(raw):
            reindexed.append(
                Chunk(
                    id=ChunkId.from_parts(
                        chunk.document_id,
                        chunk.heading_path,
                        index,
                    ),
                    document_id=chunk.document_id,
                    text=chunk.text,
                    heading_path=chunk.heading_path,
                    chunk_index=index,
                    char_range=chunk.char_range,
                    token_count=chunk.token_count,
                    content_hash=compute_content_hash(chunk.text),
                )
            )
        return tuple(reindexed)
