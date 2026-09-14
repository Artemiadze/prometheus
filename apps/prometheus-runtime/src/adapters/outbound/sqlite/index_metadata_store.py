"""SQLite-backed persistence for the authoritative index fingerprint."""

from __future__ import annotations

import sqlite3

from adapters.outbound.sqlite.errors import wrap_driver_errors
from application.dto.embedding import EmbeddingFingerprint
from application.dto.index_fingerprint import IndexFingerprint


class SqliteIndexMetadataStore:
    """Persist the single-row ``index_meta`` fingerprint (Architecture.md, section 13)."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @wrap_driver_errors
    def load(self) -> IndexFingerprint | None:
        row = self._connection.execute(
            """
            SELECT
                embedding_provider, embedding_model_id, embedding_dimension,
                parser_version, chunker_version, payload_schema_version,
                chunk_size, chunk_overlap
            FROM index_meta WHERE id = 1
            """
        ).fetchone()
        if row is None:
            return None
        return IndexFingerprint(
            embedding=EmbeddingFingerprint(
                provider=row["embedding_provider"],
                model_id=row["embedding_model_id"],
                dimension=row["embedding_dimension"],
            ),
            parser_version=row["parser_version"],
            chunker_version=row["chunker_version"],
            payload_schema_version=row["payload_schema_version"],
            chunk_size=row["chunk_size"],
            chunk_overlap=row["chunk_overlap"],
        )

    @wrap_driver_errors
    def save(self, fingerprint: IndexFingerprint) -> None:
        self._connection.execute(
            """
            INSERT INTO index_meta (
                id, embedding_provider, embedding_model_id, embedding_dimension,
                parser_version, chunker_version, payload_schema_version,
                chunk_size, chunk_overlap
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                embedding_provider = excluded.embedding_provider,
                embedding_model_id = excluded.embedding_model_id,
                embedding_dimension = excluded.embedding_dimension,
                parser_version = excluded.parser_version,
                chunker_version = excluded.chunker_version,
                payload_schema_version = excluded.payload_schema_version,
                chunk_size = excluded.chunk_size,
                chunk_overlap = excluded.chunk_overlap
            """,
            (
                fingerprint.embedding.provider,
                fingerprint.embedding.model_id,
                fingerprint.embedding.dimension,
                fingerprint.parser_version,
                fingerprint.chunker_version,
                fingerprint.payload_schema_version,
                fingerprint.chunk_size,
                fingerprint.chunk_overlap,
            ),
        )
