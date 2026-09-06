"""Token counting application port."""

from typing import Protocol


class TokenCounter(Protocol):
    """Count text using the active tokenizer or an adapter fallback."""

    def count(self, text: str) -> int: ...
