"""Structured grounded-answer contract and streaming JSON extraction."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

ANSWER_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "sources": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["answer", "sources"],
}

_ANSWER_KEY = re.compile(r'"answer"\s*:\s*"', re.DOTALL)


@dataclass(frozen=True, slots=True)
class ParsedAnswer:
    text: str
    cited: tuple[int, ...]


class AnswerParseError(ValueError):
    """Raised when model output does not satisfy the grounded answer contract."""


def parse_answer(raw: str, fragment_count: int) -> ParsedAnswer:
    try:
        payload = json.loads(raw.strip())
    except json.JSONDecodeError as error:
        raise AnswerParseError("invalid JSON") from error
    if not isinstance(payload, dict):
        raise AnswerParseError("expected JSON object")

    answer = payload.get("answer")
    sources = payload.get("sources")
    if not isinstance(answer, str) or not answer.strip():
        raise AnswerParseError("empty answer")
    if not isinstance(sources, list):
        raise AnswerParseError("invalid sources")

    cited: list[int] = []
    seen: set[int] = set()
    for item in sources:
        if isinstance(item, bool) or not isinstance(item, int):
            continue
        if item < 1 or item > fragment_count or item in seen:
            continue
        seen.add(item)
        cited.append(item)
    return ParsedAnswer(text=answer.strip(), cited=tuple(cited))


class AnswerStreamExtractor:
    """Incrementally decode the ``answer`` string from a streaming JSON object."""

    def __init__(self) -> None:
        self._buffer = ""
        self._content_start: int | None = None
        self._emitted = 0

    def feed(self, piece: str) -> str:
        self._buffer += piece
        self._ensure_content_start()
        if self._content_start is None:
            return ""
        decoded = _decode_json_string(self._buffer[self._content_start :])
        new_text = decoded[self._emitted :]
        self._emitted = len(decoded)
        return new_text

    def finish(self) -> str:
        return self._buffer.strip()

    def _ensure_content_start(self) -> None:
        if self._content_start is not None:
            return
        match = _ANSWER_KEY.search(self._buffer)
        if match is not None:
            self._content_start = match.end()


def _decode_json_string(raw: str) -> str:
    """Decode a JSON string prefix; tolerate an unterminated trailing fragment."""

    decoded: list[str] = []
    index = 0
    while index < len(raw):
        char = raw[index]
        if char == '"':
            break
        if char != "\\":
            decoded.append(char)
            index += 1
            continue
        if index + 1 >= len(raw):
            break
        escape = raw[index + 1]
        if escape == "u":
            if index + 5 >= len(raw):
                break
            try:
                decoded.append(chr(int(raw[index + 2 : index + 6], 16)))
            except ValueError:
                break
            index += 6
            continue
        decoded.append(_SIMPLE_ESCAPES.get(escape, escape))
        index += 2
    return "".join(decoded)


_SIMPLE_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}
