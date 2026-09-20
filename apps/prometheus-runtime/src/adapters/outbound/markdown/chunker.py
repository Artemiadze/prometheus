"""Temporary character-budget chunker until heading-aware PRM-E4 chunking."""

from __future__ import annotations

from collections.abc import Sequence

from application.dto.parsed_document import ParsedDocument
from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import compute_content_hash
from domain.value_objects.chunk_id import ChunkId


class CharBudgetChunker:
    """Split parsed blocks into stable, overlapping character windows."""

    def __init__(self, *, chunk_size: int, chunk_overlap: int) -> None:
        if chunk_size <= 0 or not 0 <= chunk_overlap < chunk_size:
            raise ValueError("invalid chunking configuration")
        self._chunk_size = chunk_size
        self._overlap = chunk_overlap

    def chunk(self, parsed_document: ParsedDocument) -> Sequence[Chunk]:
        chunks: list[Chunk] = []
        for section in parsed_document.sections:
            for block in section.blocks:
                for start, end in self._windows(block.text):
                    text = block.text[start:end]
                    index = len(chunks)
                    chunks.append(
                        Chunk(
                            id=ChunkId.from_parts(
                                parsed_document.document_id, section.heading_path, index
                            ),
                            document_id=parsed_document.document_id,
                            text=text,
                            heading_path=section.heading_path,
                            chunk_index=index,
                            char_range=CharRange(
                                block.char_range.start + start,
                                block.char_range.start + end,
                            ),
                            token_count=max(1, len(text.split())),
                            content_hash=compute_content_hash(text),
                        )
                    )
        return tuple(chunks)

    def _windows(self, text: str) -> Sequence[tuple[int, int]]:
        windows: list[tuple[int, int]] = []
        start = 0
        while start < len(text):
            end = min(start + self._chunk_size, len(text))
            windows.append((start, end))
            if end == len(text):
                break
            start = end - self._overlap
        return tuple(windows)
