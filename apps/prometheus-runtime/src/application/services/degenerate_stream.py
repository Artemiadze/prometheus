"""Detect runaway token repetition in local model streams."""

from __future__ import annotations

import re

_WORD = re.compile(r"[A-Za-z0-9_\u0370-\u03ff\u0400-\u04ff]+")


class DegenerateStreamError(ValueError):
    """Raised when generation loops on repeated tokens."""


class DegenerateStreamGuard:
    def __init__(self, *, min_same_run: int = 28, min_total_chars: int = 100) -> None:
        self._min_same_run = min_same_run
        self._min_total_chars = min_total_chars
        self._last_token = ""
        self._same_run = 0
        self._recent_tokens: list[str] = []
        self._total_chars = 0

    def check(self, text: str) -> None:
        if not text:
            return
        self._total_chars += len(text)
        tokens = [token.lower() for token in _WORD.findall(text) if len(token) >= 2]
        if not tokens:
            return
        for token in tokens:
            if token == self._last_token:
                self._same_run += 1
            else:
                self._last_token = token
                self._same_run = 1
            self._recent_tokens.append(token)
            if len(self._recent_tokens) > 96:
                self._recent_tokens = self._recent_tokens[-96:]

        if self._same_run >= self._min_same_run and self._total_chars >= self._min_total_chars:
            raise DegenerateStreamError(
                f"model repeated '{self._last_token}' {self._same_run} times",
            )

        if len(self._recent_tokens) >= 72:
            top = max(set(self._recent_tokens), key=self._recent_tokens.count)
            count = self._recent_tokens.count(top)
            if count >= 60 and count / len(self._recent_tokens) >= 0.78:
                raise DegenerateStreamError(
                    f"model repeated '{top}' {count}/{len(self._recent_tokens)} recent tokens",
                )
