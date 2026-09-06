"""Application policies shared by use cases."""

from application.services.embedding_compatibility import ensure_embedding_compatible

__all__ = ["ensure_embedding_compatible"]
