"""Document entity and canonical content hashing."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime

from domain.errors import InvariantViolationError
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath
from domain.value_objects.vault_id import VaultId

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def normalize_content(text: str) -> str:
    """Normalize transport-level text differences before hashing."""

    normalized = text.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in normalized.split("\n"))


def compute_content_hash(text: str) -> str:
    """Return the SHA-256 hash of normalized Markdown content."""

    return hashlib.sha256(normalize_content(text).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Document:
    """A Markdown document received from the plugin."""

    id: DocumentId
    vault_id: VaultId
    relative_path: RelativePath
    content: str
    revision: int
    content_hash: str
    modified_at: datetime

    def __post_init__(self) -> None:
        if self.revision < 0 or not _SHA256.fullmatch(self.content_hash):
            raise InvariantViolationError()
        if self.content_hash != compute_content_hash(self.content):
            raise InvariantViolationError()

    @classmethod
    def create(
        cls,
        *,
        id: DocumentId,
        vault_id: VaultId,
        relative_path: RelativePath | str,
        content: str,
        revision: int,
        modified_at: datetime,
        content_hash: str | None = None,
    ) -> Document:
        path = (
            relative_path
            if isinstance(relative_path, RelativePath)
            else RelativePath(relative_path)
        )
        return cls(
            id=id,
            vault_id=vault_id,
            relative_path=path,
            content=content,
            revision=revision,
            content_hash=(
                compute_content_hash(content) if content_hash is None else content_hash
            ),
            modified_at=modified_at,
        )

    def is_unchanged(self, content_hash: str) -> bool:
        """Compare content independently of filesystem timestamps."""

        return self.content_hash == content_hash

    def is_newer_than(self, other: Document) -> bool:
        """Compare monotonic revisions supplied by the plugin."""

        return self.revision > other.revision
