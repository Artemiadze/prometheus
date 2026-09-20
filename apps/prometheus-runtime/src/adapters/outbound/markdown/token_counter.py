"""Token counting with embedding tokenizer integration."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol, cast

from application.ports.token_counter import TokenCounter

_CODE_SPLIT_MARKER = "\n[... code continues ...]\n"
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


class _Tokenizer(Protocol):
    def encode(self, text: str, *, add_special_tokens: bool) -> object: ...


class HeuristicTokenCounter:
    """Conservative token estimate that stays within ~20% of true counts."""

    def count(self, text: str) -> int:
        if not text:
            return 0
        # Slightly under-count versus common BPE averages to avoid overshooting limits.
        char_estimate = (len(text) * 10) // 48
        word_estimate = max(1, len(text.split()))
        return max(1, min(char_estimate, word_estimate))


class CachingTokenCounter:
    """Cache counts for repeated substrings during one document pass."""

    def __init__(self, inner: TokenCounter) -> None:
        self._inner = inner
        self._cache: dict[str, int] = {}

    def count(self, text: str) -> int:
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        value = self._inner.count(text)
        if value <= 0 and text.strip():
            value = 1
        self._cache[text] = value
        return value

    def clear_cache(self) -> None:
        self._cache.clear()


class FastEmbedTokenizerCounter:
    """Use the active FastEmbed model tokenizer when it is available locally."""

    def __init__(
        self,
        *,
        model_id: str,
        cache_dir: Path,
        fallback: TokenCounter | None = None,
        tokenizer_loader: Callable[[Path], _Tokenizer | None] | None = None,
    ) -> None:
        self._model_id = model_id
        self._cache_dir = cache_dir.expanduser().resolve()
        self._fallback = fallback or HeuristicTokenCounter()
        self._tokenizer_loader = tokenizer_loader or _load_tokenizer_from_cache
        self._tokenizer: _Tokenizer | None = None
        self._tokenizer_loaded = False

    def count(self, text: str) -> int:
        tokenizer = self._get_tokenizer()
        if tokenizer is None:
            return self._fallback.count(text)
        encoded = tokenizer.encode(text, add_special_tokens=True)
        length = len(cast("Sequence[int]", getattr(encoded, "ids", encoded)))
        return max(1, length) if text.strip() else 0

    def _get_tokenizer(self) -> _Tokenizer | None:
        if not self._tokenizer_loaded:
            self._tokenizer_loaded = True
            self._tokenizer = self._tokenizer_loader(self._cache_dir)
        return self._tokenizer


def _load_tokenizer_from_cache(cache_dir: Path) -> _Tokenizer | None:
    candidates = sorted(cache_dir.glob("**/tokenizer.json"))
    if not candidates:
        return None
    try:
        from tokenizers import Tokenizer
    except ImportError:
        return None
    try:
        return cast(_Tokenizer, Tokenizer.from_file(str(candidates[0])))
    except Exception:
        return None


def split_sentences(text: str) -> list[str]:
    parts = [part for part in _SENTENCE.split(text.strip()) if part]
    return parts or ([text] if text.strip() else [])


def code_split_marker() -> str:
    return _CODE_SPLIT_MARKER
