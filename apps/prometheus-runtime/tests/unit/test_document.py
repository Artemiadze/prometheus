"""Tests for the Document domain entity."""

from datetime import UTC, datetime, timedelta

import pytest

from domain.entities.document import Document, compute_content_hash
from domain.errors import InvalidPathError, InvariantViolationError
from domain.value_objects.document_id import DocumentId
from domain.value_objects.vault_id import VaultId


def _document(
    content: str = "# Note\nContent\n",
    *,
    revision: int = 1,
    modified_at: datetime | None = None,
) -> Document:
    return Document.create(
        id=DocumentId("document-01"),
        vault_id=VaultId("vault-01"),
        relative_path="Notes/Note.md",
        content=content,
        revision=revision,
        modified_at=modified_at or datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_content_hash_uses_normalized_text() -> None:
    lf = "\ufeff# Note  \nContent\n"
    crlf = "# Note  \r\nContent\r\n"

    assert compute_content_hash(lf) == compute_content_hash(crlf)


def test_equal_hash_is_unchanged_regardless_of_modified_time() -> None:
    content = "# Note\nSame content"
    earlier = _document(content)
    later = _document(content, modified_at=earlier.modified_at + timedelta(days=1))

    assert earlier.is_unchanged(later.content_hash)


def test_revision_comparison_is_monotonic() -> None:
    assert _document(revision=2).is_newer_than(_document(revision=1))
    assert not _document(revision=1).is_newer_than(_document(revision=2))


def test_absolute_and_parent_paths_are_rejected() -> None:
    with pytest.raises(InvalidPathError):
        Document.create(
            id=DocumentId("document-01"),
            vault_id=VaultId("vault-01"),
            relative_path="/outside/Note.md",
            content="Note",
            revision=1,
            modified_at=datetime.now(UTC),
        )


def test_mismatched_content_hash_is_rejected_without_content_in_error() -> None:
    private_content = "private note body"

    with pytest.raises(InvariantViolationError) as caught:
        Document.create(
            id=DocumentId("document-01"),
            vault_id=VaultId("vault-01"),
            relative_path="Note.md",
            content=private_content,
            revision=1,
            content_hash="0" * 64,
            modified_at=datetime.now(UTC),
        )

    assert private_content not in str(caught.value)
