"""Vector-index application port."""

from collections.abc import Sequence
from typing import Protocol


class VectorIndex(Protocol):
    """Store and retrieve vectors within one already-scoped Vault."""

    def upsert(self, document_id: str, vectors: Sequence[Sequence[float]]) -> None: ...

    def delete_by_document(self, document_id: str) -> None: ...

    def search(self, query_vector: Sequence[float], limit: int) -> Sequence[str]: ...
