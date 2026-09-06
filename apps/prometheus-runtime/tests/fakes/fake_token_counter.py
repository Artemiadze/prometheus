"""Whitespace TokenCounter fake."""


class FakeTokenCounter:
    """Count whitespace-delimited words deterministically."""

    def count(self, text: str) -> int:
        return len(text.split())
