"""Token counting with embedding tokenizer integration."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol, cast

from application.ports.token_counter import EncodedSpan, TokenCounter

_CODE_SPLIT_MARKER = "\n[... code continues ...]\n"
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"\S+")


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

    def encode_with_offsets(self, text: str) -> EncodedSpan:
        if not text:
            return EncodedSpan(())
        offsets = tuple((match.start(), match.end()) for match in _WORD.finditer(text))
        if not offsets:
            return EncodedSpan(((0, len(text)),)) if text.strip() else EncodedSpan(())
        # Align token_count with count() when heuristic shrinks below word count.
        target = self.count(text)
        if target >= len(offsets):
            return EncodedSpan(offsets)
        return _thin_offsets(offsets, target)


class CachingTokenCounter:
    """Cache counts and offset encodings for one document pass."""

    def __init__(self, inner: TokenCounter) -> None:
        self._inner = inner
        self._count_cache: dict[str, int] = {}
        self._span_cache: dict[str, EncodedSpan] = {}
        self.encode_calls = 0

    def count(self, text: str) -> int:
        cached = self._count_cache.get(text)
        if cached is not None:
            return cached
        value = self._inner.count(text)
        if value <= 0 and text.strip():
            value = 1
        self._count_cache[text] = value
        return value

    def encode_with_offsets(self, text: str) -> EncodedSpan:
        cached = self._span_cache.get(text)
        if cached is not None:
            return cached
        self.encode_calls += 1
        span = self._inner.encode_with_offsets(text)
        self._span_cache[text] = span
        self._count_cache.setdefault(text, span.token_count if text.strip() else 0)
        return span

    def clear_cache(self) -> None:
        self._count_cache.clear()
        self._span_cache.clear()
        self.encode_calls = 0


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
        span = self.encode_with_offsets(text)
        if not text.strip():
            return 0
        return max(1, span.token_count)

    def encode_with_offsets(self, text: str) -> EncodedSpan:
        if not text:
            return EncodedSpan(())
        tokenizer = self._get_tokenizer()
        if tokenizer is None:
            return self._fallback.encode_with_offsets(text)
        encoded = tokenizer.encode(text, add_special_tokens=False)
        raw_offsets = cast("Sequence[tuple[int, int]]", getattr(encoded, "offsets", ()))
        offsets = tuple(
            (start, end) for start, end in raw_offsets if isinstance(start, int) and end > start
        )
        if offsets:
            return EncodedSpan(offsets)
        # Tokenizer returned no usable offsets; fall back to length-based span.
        count = len(cast("Sequence[int]", getattr(encoded, "ids", encoded)))
        if count <= 0:
            return self._fallback.encode_with_offsets(text)
        return _uniform_offsets(text, count)

    def _get_tokenizer(self) -> _Tokenizer | None:
        if not self._tokenizer_loaded:
            self._tokenizer_loaded = True
            self._tokenizer = self._tokenizer_loader(self._cache_dir)
        return self._tokenizer


def _thin_offsets(
    offsets: tuple[tuple[int, int], ...],
    target: int,
) -> EncodedSpan:
    """Reduce offset list to ``target`` spans by merging adjacent ranges."""

    if target <= 0:
        return EncodedSpan(())
    if target >= len(offsets):
        return EncodedSpan(offsets)
    merged: list[tuple[int, int]] = []
    n = len(offsets)
    for i in range(target):
        start_i = (i * n) // target
        end_i = ((i + 1) * n) // target - 1
        merged.append((offsets[start_i][0], offsets[end_i][1]))
    return EncodedSpan(tuple(merged))


def _uniform_offsets(text: str, token_count: int) -> EncodedSpan:
    if token_count <= 0:
        return EncodedSpan(())
    n = len(text)
    return EncodedSpan(
        tuple(
            ((i * n) // token_count, max((i * n) // token_count, ((i + 1) * n) // token_count))
            for i in range(token_count)
        )
    )


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
