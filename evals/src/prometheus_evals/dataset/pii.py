"""Heuristic PII patterns that must not appear in public eval corpora."""

from __future__ import annotations

import re
from collections.abc import Iterable

_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")
_HOME_PATH = re.compile(r"(?:/home/|/Users/)[^\s]+")
_PRIVATE_URL = re.compile(
    r"https?://(?:localhost|127\.0\.0\.1|192\.168\.|10\.\d+\.|172\.(?:1[6-9]|2\d|3[01])\.)[^\s]*",
    re.IGNORECASE,
)


def find_pii_violations(text: str) -> list[str]:
    """Return human-readable descriptions of PII-like patterns found in text."""

    violations: list[str] = []
    for pattern, label in (
        (_EMAIL, "email"),
        (_PHONE, "phone"),
        (_HOME_PATH, "home path"),
        (_PRIVATE_URL, "private URL"),
    ):
        match = pattern.search(text)
        if match is not None:
            violations.append(f"{label}: {match.group(0)!r}")
    return violations


def assert_no_pii(texts: Iterable[str]) -> None:
    problems: list[str] = []
    for text in texts:
        problems.extend(find_pii_violations(text))
    if problems:
        joined = "; ".join(problems[:10])
        raise ValueError(f"PII-like content detected: {joined}")
