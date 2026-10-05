"""Tests for structured grounded answer parsing and streaming extraction."""

from __future__ import annotations

import json

import pytest

from application.services.answer_contract import (
    AnswerParseError,
    AnswerStreamExtractor,
    parse_answer,
    try_parse_answer,
)


def test_parse_answer_accepts_valid_payload_and_filters_invalid_sources() -> None:
    raw = json.dumps({"answer": "sqlite3", "sources": [1, 99, 1, 2, "x"]})

    parsed = parse_answer(raw, fragment_count=2)

    assert parsed.text == "sqlite3"
    assert parsed.cited == (1, 2)


def test_parse_answer_rejects_empty_answer() -> None:
    with pytest.raises(AnswerParseError, match="empty answer"):
        parse_answer('{"answer":"   ","sources":[]}', fragment_count=1)


@pytest.mark.parametrize("size", [1, 2, 3, 7])
def test_stream_extractor_decodes_answer_across_fragment_boundaries(size: int) -> None:
    payload = json.dumps({"answer": "line1\nline2", "sources": [1]}, ensure_ascii=False)
    pieces = [payload[index : index + size] for index in range(0, len(payload), size)]
    extractor = AnswerStreamExtractor()

    emitted = ""
    for piece in pieces:
        emitted += extractor.feed(piece)

    assert emitted == "line1\nline2"
    assert parse_answer(extractor.finish(), fragment_count=1).text == "line1\nline2"


def test_try_parse_answer_recovers_from_trailing_garbage() -> None:
    raw = '{"answer":"sqlite3","sources":[1,2]} trailing garbage'

    parsed = try_parse_answer(raw, fragment_count=3)

    assert parsed is not None
    assert parsed.text == "sqlite3"
    assert parsed.cited == (1, 2)


def test_try_parse_answer_returns_none_when_answer_missing() -> None:
    assert try_parse_answer('{"sources":[1]}', fragment_count=1) is None


def test_stream_extractor_emits_only_new_answer_characters() -> None:
    extractor = AnswerStreamExtractor()

    assert extractor.feed('{"answer":"hel') == "hel"
    assert extractor.feed('lo"') == "lo"
    assert extractor.finish() == '{"answer":"hello"'
