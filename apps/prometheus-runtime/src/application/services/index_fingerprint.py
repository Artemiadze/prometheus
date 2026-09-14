"""Compatibility guard for the full index fingerprint (Architecture.md, section 13)."""

from application.dto.index_fingerprint import IndexFingerprint
from application.errors import IndexRebuildRequiredError


def ensure_index_compatible(stored: IndexFingerprint | None, active: IndexFingerprint) -> None:
    """Require a full rebuild when a previously stored fingerprint no longer matches.

    ``stored`` is ``None`` on the very first run for a Vault; that is not a mismatch,
    it is simply the absence of an index yet to be created.
    """

    if stored is not None and stored != active:
        raise IndexRebuildRequiredError()
