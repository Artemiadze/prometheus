"""Document persistence application port."""

from collections.abc import Sequence
from typing import Protocol


class DocumentRepository(Protocol):
    """Read persisted document state within one already-scoped Vault."""

    def get_revision(self, document_id: str) -> str | None: ...

    def list_paths(self) -> Sequence[str]: ...
