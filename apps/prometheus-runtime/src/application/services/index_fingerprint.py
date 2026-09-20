"""Compatibility guard for the full index fingerprint (Architecture.md, section 13)."""

from __future__ import annotations

from application.dto.index_fingerprint import IndexFingerprint
from application.errors import IndexRebuildRequiredError


def ensure_index_compatible(stored: IndexFingerprint | None, active: IndexFingerprint) -> None:
    """Require a full rebuild when a previously stored fingerprint no longer matches.

    ``stored`` is ``None`` on the very first run for a Vault; that is not a mismatch,
    it is simply the absence of an index yet to be created.
    """

    if stored is None or stored == active:
        return
    raise IndexRebuildRequiredError(describe_fingerprint_mismatch(stored, active))


def describe_fingerprint_mismatch(stored: IndexFingerprint, active: IndexFingerprint) -> str:
    """Return a presentation-safe summary of which fingerprint fields diverged."""

    changes: list[str] = []
    if stored.embedding.provider != active.embedding.provider:
        changes.append(
            f"embedding.provider: {stored.embedding.provider!r} -> {active.embedding.provider!r}"
        )
    if stored.embedding.model_id != active.embedding.model_id:
        changes.append(
            f"embedding.model_id: {stored.embedding.model_id!r} -> {active.embedding.model_id!r}"
        )
    if stored.embedding.dimension != active.embedding.dimension:
        changes.append(
            f"embedding.dimension: {stored.embedding.dimension} -> {active.embedding.dimension}"
        )
    if stored.parser_version != active.parser_version:
        changes.append(f"parser_version: {stored.parser_version} -> {active.parser_version}")
    if stored.chunker_version != active.chunker_version:
        changes.append(f"chunker_version: {stored.chunker_version} -> {active.chunker_version}")
    if stored.payload_schema_version != active.payload_schema_version:
        changes.append(
            "payload_schema_version: "
            f"{stored.payload_schema_version} -> {active.payload_schema_version}"
        )
    if stored.chunk_size != active.chunk_size:
        changes.append(f"chunk_size: {stored.chunk_size} -> {active.chunk_size}")
    if stored.chunk_overlap != active.chunk_overlap:
        changes.append(f"chunk_overlap: {stored.chunk_overlap} -> {active.chunk_overlap}")
    if not changes:
        return "Index fingerprint changed; rebuild the index"
    return "Index rebuild required: " + "; ".join(changes)
