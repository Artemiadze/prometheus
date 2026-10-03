"""One-block-per-chunk Chunker fake."""

from collections.abc import Sequence

from application.dto.parsed_document import ParsedDocument
from domain.entities.chunk import Chunk
from domain.entities.document import compute_content_hash
from domain.value_objects.chunk_id import ChunkId


class FakeChunker:
    """Convert each parsed block into one deterministic Chunk."""

    def chunk(self, parsed_document: ParsedDocument) -> Sequence[Chunk]:
        chunks: list[Chunk] = []
        for section in parsed_document.sections:
            for block in section.blocks:
                index = len(chunks)
                chunks.append(
                    Chunk(
                        id=ChunkId.from_parts(
                            parsed_document.document_id,
                            section.heading_path,
                            section.section_ordinal,
                            index,
                        ),
                        document_id=parsed_document.document_id,
                        text=block.text,
                        heading_path=section.heading_path,
                        chunk_index=index,
                        char_range=block.char_range,
                        token_count=max(1, len(block.text.split())),
                        content_hash=compute_content_hash(block.text),
                        heading_line=section.heading_line,
                        heading_occurrence=section.heading_occurrence,
                    )
                )
        return tuple(chunks)
