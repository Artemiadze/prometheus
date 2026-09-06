"""Document identifier value object."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from domain.errors import InvalidIdentifierError
from domain.value_objects.relative_path import RelativePath

_DOCUMENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{5,127}$")


@dataclass(frozen=True, slots=True)
class DocumentId:
    """An opaque stable ID, optionally derived from a normalized relative path."""

    value: str

    def __post_init__(self) -> None:
        if not _DOCUMENT_ID.fullmatch(self.value):
            raise InvalidIdentifierError()

    @classmethod
    def from_relative_path(cls, path: RelativePath | str) -> DocumentId:
        normalized = path if isinstance(path, RelativePath) else RelativePath(path)
        digest = hashlib.sha256(normalized.value.encode("utf-8")).hexdigest()
        return cls(digest[:32])

    def __str__(self) -> str:
        return self.value
