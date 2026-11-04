"""Token counting application port."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EncodedSpan:
    """One encode pass: token count plus char offsets per token.

    ``offsets[i]`` is ``(start_char, end_char)`` for token ``i`` in the source text.
    Empty or zero-width entries are omitted by producers when possible.
    """

    offsets: tuple[tuple[int, int], ...]

    @property
    def token_count(self) -> int:
        return len(self.offsets)

    def window_char_end(self, start_token: int, max_tokens: int) -> int:
        """Exclusive character end of ``tokens[start_token:start_token + max_tokens]``."""

        if not self.offsets or start_token >= len(self.offsets) or max_tokens <= 0:
            return self.offsets[-1][1] if self.offsets else 0
        end_token = min(start_token + max_tokens, len(self.offsets))
        return self.offsets[end_token - 1][1]

    def overlap_char_start(self, overlap_tokens: int) -> int:
        """Character start of the last ``overlap_tokens`` tokens (or 0 if fewer)."""

        if overlap_tokens <= 0 or not self.offsets:
            return self.offsets[-1][1] if self.offsets else 0
        if overlap_tokens >= len(self.offsets):
            return self.offsets[0][0]
        return self.offsets[len(self.offsets) - overlap_tokens][0]


class TokenCounter(Protocol):
    """Count text using the active tokenizer or an adapter fallback."""

    def count(self, text: str) -> int: ...

    def encode_with_offsets(self, text: str) -> EncodedSpan: ...
