"""Application policies shared by use cases."""

from application.services.embedding_compatibility import ensure_embedding_compatible
from application.services.index_fingerprint import ensure_index_compatible
from application.services.indexing_transaction import (
    remove_document_index,
    replace_document_index,
)

__all__ = [
    "ensure_embedding_compatible",
    "ensure_index_compatible",
    "remove_document_index",
    "replace_document_index",
]
