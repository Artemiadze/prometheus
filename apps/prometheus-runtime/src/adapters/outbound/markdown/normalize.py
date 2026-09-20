"""Document normalization and YAML frontmatter extraction (PRM-21)."""

from __future__ import annotations

import re

from domain.entities.document import compute_content_hash, normalize_content

_INVISIBLE = re.compile(r"[\u200b-\u200d\ufeff\ufe00-\ufe0f]")
_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
_FRONTMATTER_LINE = re.compile(r"^([A-Za-z0-9_.-]+)\s*:\s*(.*)$")


def strip_invisible_characters(text: str) -> str:
    """Remove zero-width and similar characters beyond transport normalization."""

    return _INVISIBLE.sub("", text)


def split_frontmatter(text: str) -> tuple[tuple[tuple[str, str], ...], str, int]:
    """Return frontmatter pairs, full normalized text, and body start offset."""

    normalized = normalize_content(strip_invisible_characters(text))
    match = _FRONTMATTER.match(normalized)
    if match is None:
        return (), normalized, 0

    raw_frontmatter = match.group(1)
    pairs: list[tuple[str, str]] = []
    for line in raw_frontmatter.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        field = _FRONTMATTER_LINE.match(stripped)
        if field is None:
            continue
        pairs.append((field.group(1), field.group(2).strip()))

    body_start = match.end()
    return tuple(pairs), normalized, body_start


def normalized_content_hash(text: str) -> str:
    """Stable hash over normalized transport text including optional frontmatter."""

    return compute_content_hash(strip_invisible_characters(text))
