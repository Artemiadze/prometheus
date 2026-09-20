"""Temporary whitespace token counter until tokenizer integration from PRM-E4."""

import re

_WORD = re.compile(r"\S+")


class WhitespaceTokenCounter:
    """Approximate token use by counting whitespace-delimited words."""

    def count(self, text: str) -> int:
        return len(_WORD.findall(text))
