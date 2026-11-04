"""Tests for PRM-E4 Markdown normalization, parsing, and chunking."""

from datetime import UTC, datetime

from adapters.outbound.markdown.chunker import HeadingAwareChunker
from adapters.outbound.markdown.normalize import (
    normalized_content_hash,
    split_frontmatter,
)
from adapters.outbound.markdown.parser import ObsidianMarkdownParser
from adapters.outbound.markdown.token_counter import (
    CachingTokenCounter,
    HeuristicTokenCounter,
)
from application.dto.parsed_document import BlockKind, ParsedDocument
from domain.entities.document import Document
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId
from domain.value_objects.vault_id import VaultId


def _document(content: str) -> Document:
    return Document.create(
        id=DocumentId("document-01"),
        vault_id=VaultId("vault-01"),
        relative_path="Notes/Note.md",
        content=content,
        revision=1,
        modified_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_frontmatter_is_metadata_not_body() -> None:
    raw = "---\ntitle: Note\n---\n# Title\nBody\n"
    frontmatter, normalized, body_start = split_frontmatter(raw)
    assert frontmatter == (("title", "Note"),)
    assert normalized[body_start:].startswith("# Title")

    parsed = ObsidianMarkdownParser().parse(_document(raw))
    assert parsed.frontmatter == (("title", "Note"),)
    assert all(
        "title:" not in block.text for section in parsed.sections for block in section.blocks
    )


def test_equal_hash_with_different_eol() -> None:
    assert normalized_content_hash("a\r\nb") == normalized_content_hash("a\nb")


def test_empty_document_parses_without_error() -> None:
    parsed = ObsidianMarkdownParser().parse(_document(""))
    assert parsed.sections == ()


def test_heading_inside_fence_is_not_a_section() -> None:
    content = "```\n# Not a heading\n```\n# Real\nText\n"
    parsed = ObsidianMarkdownParser().parse(_document(content))
    paths = [section.heading_path for section in parsed.sections]
    assert ("Real",) in paths
    assert all("Not a heading" not in heading for path in paths for heading in path)
    code_blocks = [
        block
        for section in parsed.sections
        for block in section.blocks
        if block.kind == BlockKind.CODE
    ]
    assert any("# Not a heading" in block.text for block in code_blocks)


def test_list_and_table_blocks_stay_intact() -> None:
    content = "# Topic\n\n- one\n- two\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"
    parsed = ObsidianMarkdownParser().parse(_document(content))
    kinds = [block.kind for block in parsed.sections[0].blocks]
    assert BlockKind.LIST in kinds
    assert BlockKind.TABLE in kinds
    list_block = next(block for block in parsed.sections[0].blocks if block.kind == BlockKind.LIST)
    assert "- one" in list_block.text and "- two" in list_block.text


def test_section_exposes_full_heading_path() -> None:
    content = "# Root\n\n## Child\n\nParagraph\n"
    parsed = ObsidianMarkdownParser().parse(_document(content))
    child = next(
        section for section in parsed.sections if section.heading_path == ("Root", "Child")
    )
    assert child.level == 2


def test_heuristic_fallback_does_not_overshoot_reference() -> None:
    corpus = (
        "Short note.",
        "A slightly longer paragraph with several words in English.",
        "def foo():\n    return 42\n",
        "Заголовок и несколько слов на русском языке.",
    )
    heuristic = HeuristicTokenCounter()

    def reference_count(text: str) -> int:
        return max(1, len(text.split()))

    for sample in corpus:
        assert heuristic.count(sample) <= reference_count(sample) * 1.2


def test_token_counter_caches_within_document_pass() -> None:
    counter = CachingTokenCounter(HeuristicTokenCounter())
    first = counter.count("repeat me")
    second = counter.count("repeat me")
    counter.clear_cache()
    third = counter.count("repeat me")
    assert first == second == third


def test_small_section_becomes_single_chunk() -> None:
    content = "# PostgreSQL\n\n## Indexes\n\nOne small paragraph.\n"
    parsed = ObsidianMarkdownParser().parse(_document(content))
    chunker = HeadingAwareChunker(
        max_tokens=100,
        overlap_tokens=10,
        token_counter=HeuristicTokenCounter(),
    )
    section = next(
        section for section in parsed.sections if section.heading_path == ("PostgreSQL", "Indexes")
    )
    chunks = chunker.chunk(ParsedDocument(parsed.document_id, (section,), parsed.frontmatter))
    assert len(chunks) == 1
    assert chunks[0].heading_path == ("PostgreSQL", "Indexes")


def test_chunk_ids_are_stable_per_section_index() -> None:
    content = "# A\n\npara one\n\n# B\n\npara two\n"
    document = _document(content)
    parser = ObsidianMarkdownParser()
    chunker = HeadingAwareChunker(
        max_tokens=200,
        overlap_tokens=0,
        token_counter=HeuristicTokenCounter(),
    )
    first = chunker.chunk(parser.parse(document))
    second = chunker.chunk(parser.parse(document))
    assert [chunk.id for chunk in first] == [chunk.id for chunk in second]

    edited = _document("# A\n\npara one changed\n\n# B\n\npara two\n")
    edited_chunks = chunker.chunk(parser.parse(edited))
    b_chunk = next(chunk for chunk in edited_chunks if chunk.heading_path == ("B",))
    unchanged = next(chunk for chunk in edited_chunks if chunk.heading_path == ("A",))
    assert unchanged.id == next(chunk for chunk in first if chunk.heading_path == ("A",)).id
    assert b_chunk.id == next(chunk for chunk in first if chunk.heading_path == ("B",)).id


def test_duplicate_heading_sections_get_distinct_chunk_ids_and_occurrences() -> None:
    content = "## Notes\n\nfirst body\n\n## Notes\n\nsecond body\n"
    parsed = ObsidianMarkdownParser().parse(_document(content))
    notes_sections = [section for section in parsed.sections if section.heading_path == ("Notes",)]
    assert len(notes_sections) == 2
    assert notes_sections[0].heading_occurrence == 1
    assert notes_sections[1].heading_occurrence == 2
    assert notes_sections[0].heading_line != notes_sections[1].heading_line
    chunker = HeadingAwareChunker(
        max_tokens=100,
        overlap_tokens=0,
        token_counter=HeuristicTokenCounter(),
    )
    chunks = chunker.chunk(parsed)
    assert len(chunks) == 2
    assert chunks[0].id != chunks[1].id
    assert [chunk.chunk_index for chunk in chunks] == [0, 1]


def test_chunks_do_not_reuse_chunk_index_within_section() -> None:
    long_body = "word " * 400
    content = f"# Section\n\n{long_body}"
    parsed = ObsidianMarkdownParser().parse(_document(content))
    chunker = HeadingAwareChunker(
        max_tokens=50,
        overlap_tokens=5,
        token_counter=HeuristicTokenCounter(),
    )
    chunks = chunker.chunk(parsed)
    section_chunks = [chunk for chunk in chunks if chunk.heading_path == ("Section",)]
    indices = [chunk.chunk_index for chunk in section_chunks]
    assert len(indices) == len(set(indices))
    assert all(chunk.token_count <= 50 for chunk in section_chunks)


def test_encoded_span_window_and_overlap_helpers() -> None:
    from application.ports.token_counter import EncodedSpan

    span = EncodedSpan(((0, 2), (3, 5), (6, 8), (9, 11)))
    assert span.token_count == 4
    assert span.window_char_end(0, 2) == 5
    assert span.window_char_end(2, 10) == 11
    assert span.overlap_char_start(2) == 6
    assert span.overlap_char_start(10) == 0


def test_heuristic_encode_with_offsets_matches_words() -> None:
    counter = HeuristicTokenCounter()
    span = counter.encode_with_offsets("alpha beta gamma")
    assert span.token_count == counter.count("alpha beta gamma")
    assert span.offsets[0] == (0, 5)
    assert span.offsets[-1][1] == 16


def test_fastembed_counter_uses_offsets_when_tokenizer_present() -> None:
    from adapters.outbound.markdown.token_counter import FastEmbedTokenizerCounter

    class _Encoding:
        def __init__(self) -> None:
            self.ids = [1, 2, 3]
            self.offsets = [(0, 3), (4, 7), (8, 11)]

    class _Tokenizer:
        def encode(self, text: str, *, add_special_tokens: bool) -> _Encoding:
            assert add_special_tokens is False
            return _Encoding()

    counter = FastEmbedTokenizerCounter(
        model_id="fake",
        cache_dir=__import__("pathlib").Path("."),
        tokenizer_loader=lambda _path: _Tokenizer(),
    )
    span = counter.encode_with_offsets("foo bar baz")
    assert span.offsets == ((0, 3), (4, 7), (8, 11))
    assert counter.count("foo bar baz") == 3


def test_long_split_uses_few_encode_passes() -> None:
    from fakes.fake_token_counter import FakeTokenCounter

    long_body = "word " * 400
    content = f"# Section\n\n{long_body}"
    parsed = ObsidianMarkdownParser().parse(_document(content))
    counter = FakeTokenCounter()
    caching = CachingTokenCounter(counter)
    chunker = HeadingAwareChunker(
        max_tokens=50,
        overlap_tokens=5,
        token_counter=caching,
    )
    chunks = chunker.chunk(parsed)
    assert len(chunks) > 1
    # Offset-based splitting should encode each oversized piece once (plus overlap
    # encodes on adjacent joins), not once per character of the overlap window.
    assert caching.encode_calls < 40


def test_token_window_split_covers_source_with_overlap() -> None:
    from fakes.fake_token_counter import FakeTokenCounter

    body = " ".join(f"tok{i}" for i in range(120))
    content = f"# Section\n\n{body}"
    parsed = ObsidianMarkdownParser().parse(_document(content))
    chunker = HeadingAwareChunker(
        max_tokens=20,
        overlap_tokens=4,
        token_counter=FakeTokenCounter(),
    )
    chunks = chunker.chunk(parsed)
    section_chunks = [chunk for chunk in chunks if chunk.heading_path == ("Section",)]
    assert len(section_chunks) > 1
    assert all(chunk.token_count <= 20 for chunk in section_chunks)
    joined = " ".join(chunk.text for chunk in section_chunks)
    assert "tok0" in section_chunks[0].text
    assert "tok119" in section_chunks[-1].text
    assert "tok50" in joined


def test_stable_chunk_id_from_parts() -> None:
    document_id = DocumentId("document-01")
    expected = ChunkId.from_parts(document_id, ("Heading",), 1, 0)
    again = ChunkId.from_parts(document_id, ("Heading",), 1, 0)
    assert expected == again
