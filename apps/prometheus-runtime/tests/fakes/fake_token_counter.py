"""Whitespace TokenCounter fake."""

from __future__ import annotations

import re

from application.ports.token_counter import EncodedSpan

_WORD = re.compile(r"\S+")


class FakeTokenCounter:
    """Count whitespace-delimited words deterministically."""

    def __init__(self) -> None:
        self.encode_calls = 0

    def count(self, text: str) -> int:
        return len(text.split())

    def encode_with_offsets(self, text: str) -> EncodedSpan:
        self.encode_calls += 1
        if not text:
            return EncodedSpan(())
        offsets = tuple((match.start(), match.end()) for match in _WORD.finditer(text))
        if offsets:
            return EncodedSpan(offsets)
        return EncodedSpan(((0, len(text)),)) if text.strip() else EncodedSpan(())
