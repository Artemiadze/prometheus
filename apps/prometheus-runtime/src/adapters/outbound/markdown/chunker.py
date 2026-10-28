"""Heading-aware chunking with cascade splits and overlap."""

from __future__ import annotations

from collections.abc import Sequence

from adapters.outbound.markdown.token_counter import CachingTokenCounter, code_split_marker
from application.dto.parsed_document import ParsedDocument, ParsedSection
from application.ports.token_counter import TokenCounter
from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import compute_content_hash
from domain.value_objects.chunk_id import ChunkId


class HeadingAwareChunker:
    """Split parsed Markdown into retrieval chunks bounded by token budget."""

    def __init__(
        self,
        *,
        max_tokens: int,
        overlap_tokens: int,
        token_counter: TokenCounter,
    ) -> None:
        if max_tokens <= 0 or not 0 <= overlap_tokens < max_tokens:
            raise ValueError("invalid chunking configuration")
        self._max_tokens = max_tokens
        self._overlap = overlap_tokens
        self._tokens = (
            token_counter
            if isinstance(token_counter, CachingTokenCounter)
            else CachingTokenCounter(token_counter)
        )
        self._sep_tokens = self._tokens.count("\n\n")

    def chunk(self, parsed_document: ParsedDocument) -> Sequence[Chunk]:
        self._tokens.clear_cache()
        self._sep_tokens = self._tokens.count("\n\n")
        chunks: list[Chunk] = []
        chunk_index = 0
        for section in parsed_document.sections:
            for piece in self._chunk_section(parsed_document.document_id, section, chunk_index):
                chunks.append(piece)
                chunk_index += 1
        return tuple(chunks)

    def _chunk_section(
        self,
        document_id: object,
        section: ParsedSection,
        start_index: int,
    ) -> list[Chunk]:
        from domain.value_objects.document_id import DocumentId

        assert isinstance(document_id, DocumentId)
        pieces = self._section_pieces(section)
        if not pieces:
            return []

        raw_chunks: list[tuple[str, CharRange]] = []
        for group in self._pack_block_groups(pieces):
            group_text = "\n\n".join(text for text, _ in group)
            group_range = CharRange(group[0][1].start, group[-1][1].end)
            if self._tokens.count(group_text) <= self._max_tokens:
                raw_chunks.append((group_text, group_range))
                continue
            for text, char_range in group:
                raw_chunks.extend(self._split_block(text, char_range))
        raw_chunks = self._apply_overlap(raw_chunks)
        return [
            self._make_chunk(
                document_id=document_id,
                section=section,
                chunk_index=start_index + index,
                text=text,
                char_range=char_range,
            )
            for index, (text, char_range) in enumerate(raw_chunks)
        ]

    def _section_pieces(self, section: ParsedSection) -> list[tuple[str, CharRange]]:
        return [(block.text, block.char_range) for block in section.blocks]

    def _pack_block_groups(
        self,
        pieces: list[tuple[str, CharRange]],
    ) -> list[list[tuple[str, CharRange]]]:
        """Pack blocks using per-piece token counts (no re-encode of the growing join)."""

        groups: list[list[tuple[str, CharRange]]] = []
        current: list[tuple[str, CharRange]] = []
        current_tokens = 0
        for piece in pieces:
            piece_tokens = self._tokens.count(piece[0])
            if current:
                projected = current_tokens + self._sep_tokens + piece_tokens
                if projected > self._max_tokens:
                    groups.append(current)
                    current = [piece]
                    current_tokens = piece_tokens
                    continue
                current.append(piece)
                current_tokens = projected
            else:
                current = [piece]
                current_tokens = piece_tokens
        if current:
            groups.append(current)
        return groups

    def _split_block(self, text: str, char_range: CharRange) -> list[tuple[str, CharRange]]:
        if self._tokens.count(text) <= self._max_tokens:
            return [(text, char_range)]

        paragraphs = _split_paragraphs(text)
        if len(paragraphs) > 1:
            return self._split_units(paragraphs, char_range.start)

        from adapters.outbound.markdown.token_counter import split_sentences

        sentences = split_sentences(text)
        if len(sentences) > 1:
            return self._split_units(sentences, char_range.start)

        return self._split_by_tokens(text, char_range.start, allow_code_marker=False)

    def _split_units(
        self,
        units: list[str],
        absolute_start: int,
    ) -> list[tuple[str, CharRange]]:
        chunks: list[tuple[str, CharRange]] = []
        current_parts: list[str] = []
        current_tokens = 0
        current_start = absolute_start
        cursor = absolute_start
        for unit in units:
            unit_tokens = self._tokens.count(unit)
            if current_parts:
                projected = current_tokens + self._sep_tokens + unit_tokens
                if projected > self._max_tokens:
                    text = "\n\n".join(current_parts)
                    chunks.append((text, CharRange(current_start, cursor)))
                    current_parts = [unit]
                    current_tokens = unit_tokens
                    current_start = cursor
                    cursor = current_start + len(unit)
                    continue
                current_parts.append(unit)
                current_tokens = projected
                cursor = current_start + len("\n\n".join(current_parts))
            else:
                current_parts = [unit]
                current_tokens = unit_tokens
                current_start = cursor
                cursor = current_start + len(unit)
        if current_parts:
            text = "\n\n".join(current_parts)
            chunks.append((text, CharRange(current_start, current_start + len(text))))
        return self._refine_oversized(chunks)

    def _refine_oversized(
        self,
        chunks: list[tuple[str, CharRange]],
    ) -> list[tuple[str, CharRange]]:
        refined: list[tuple[str, CharRange]] = []
        for text, char_range in chunks:
            if self._tokens.count(text) <= self._max_tokens:
                refined.append((text, char_range))
            else:
                refined.extend(
                    self._split_by_tokens(text, char_range.start, allow_code_marker=True)
                )
        return refined

    def _split_by_tokens(
        self,
        text: str,
        absolute_start: int,
        *,
        allow_code_marker: bool,
    ) -> list[tuple[str, CharRange]]:
        """Split using a single encode_with_offsets pass and token-index windows."""

        span = self._tokens.encode_with_offsets(text)
        if span.token_count == 0:
            return [(text, CharRange(absolute_start, absolute_start + len(text)))] if text else []
        if span.token_count <= self._max_tokens:
            return [(text, CharRange(absolute_start, absolute_start + len(text)))]

        marker = code_split_marker() if allow_code_marker else ""
        chunks: list[tuple[str, CharRange]] = []
        token_i = 0
        while token_i < span.token_count:
            end_token = min(token_i + self._max_tokens, span.token_count)
            char_start = span.offsets[token_i][0]
            char_end = span.window_char_end(token_i, self._max_tokens)
            if char_end <= char_start:
                char_end = min(char_start + 1, len(text))
            piece = text[char_start:char_end]
            if marker and token_i > 0:
                piece = f"{marker}{piece}"
            if marker and end_token < span.token_count:
                piece = f"{piece}{marker}"
            chunks.append(
                (piece, CharRange(absolute_start + char_start, absolute_start + char_end))
            )
            if end_token >= span.token_count:
                break
            next_i = end_token - self._overlap if self._overlap > 0 else end_token
            token_i = max(token_i + 1, next_i)
        return chunks

    def _apply_overlap(
        self,
        chunks: list[tuple[str, CharRange]],
    ) -> list[tuple[str, CharRange]]:
        if self._overlap <= 0 or len(chunks) < 2:
            return chunks
        merged: list[tuple[str, CharRange]] = [chunks[0]]
        for text, char_range in chunks[1:]:
            prev_text, prev_range = merged[-1]
            span = self._tokens.encode_with_offsets(prev_text)
            tail_start = span.overlap_char_start(self._overlap)
            prefix = prev_text[tail_start:]
            combined = f"{prefix}{text}" if prefix else text
            if prefix and self._tokens.count(combined) <= self._max_tokens:
                merged[-1] = (combined, CharRange(prev_range.start + tail_start, char_range.end))
            else:
                merged.append((text, char_range))
        return merged

    def _make_chunk(
        self,
        *,
        document_id: object,
        section: ParsedSection,
        chunk_index: int,
        text: str,
        char_range: CharRange,
    ) -> Chunk:
        from domain.value_objects.document_id import DocumentId

        assert isinstance(document_id, DocumentId)
        if not text.strip():
            raise ValueError("chunk text must not be blank")
        token_count = self._tokens.count(text)
        return Chunk(
            id=ChunkId.from_parts(
                document_id,
                section.heading_path,
                section.section_ordinal,
                chunk_index,
            ),
            document_id=document_id,
            text=text,
            heading_path=section.heading_path,
            chunk_index=chunk_index,
            char_range=char_range,
            token_count=max(1, token_count),
            content_hash=compute_content_hash(text),
            heading_line=section.heading_line,
            heading_occurrence=section.heading_occurrence,
        )


def _split_paragraphs(text: str) -> list[str]:
    parts = [part.strip() for part in text.split("\n\n") if part.strip()]
    return parts
