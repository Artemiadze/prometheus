"""Tests for removing model reasoning traces from Ollama output."""

from __future__ import annotations

import pytest

from adapters.outbound.ollama.reasoning import ReasoningFilter, strip_reasoning


def _stream(pieces: list[str]) -> str:
    reasoning_filter = ReasoningFilter()
    return (
        "".join(reasoning_filter.feed(piece) for piece in pieces)
        + reasoning_filter.flush()
    )


def test_leading_reasoning_block_is_removed() -> None:
    text = "<think>\nI need to look at the context.\n</think>\n\n```bash\nsqlite3\n```"

    assert strip_reasoning(text) == "```bash\nsqlite3\n```"


def test_text_without_reasoning_is_unchanged() -> None:
    assert (
        strip_reasoning("Use `a < b` and <b>bold</b>.")
        == "Use `a < b` and <b>bold</b>."
    )


def test_unterminated_reasoning_block_is_discarded() -> None:
    assert strip_reasoning("<think>still reasoning") == ""


@pytest.mark.parametrize("size", [1, 2, 3, 5, 8])
def test_tags_split_across_stream_fragments_are_removed(size: int) -> None:
    text = "<think>reasoning</think>\nAnswer: <thin is fine"
    pieces = [text[i : i + size] for i in range(0, len(text), size)]

    assert _stream(pieces) == "Answer: <thin is fine"
