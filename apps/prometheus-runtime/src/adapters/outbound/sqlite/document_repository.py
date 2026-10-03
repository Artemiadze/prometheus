"""SQLite-backed manifest repository (documents + chunks, never note text)."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import datetime

from adapters.outbound.sqlite.errors import wrap_driver_errors
from application.dto.document_state import DocumentState
from domain.entities.chunk import Chunk
from domain.entities.document import Document
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath


class SqliteDocumentRepository:
    """Persist manifest state for one Vault-scoped SQLite connection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @wrap_driver_errors
    def get_state(self, document_id: DocumentId) -> DocumentState | None:
        row = self._connection.execute(
            """
            SELECT
                d.document_id, d.relative_path, d.revision, d.content_hash,
                d.modified_at, d.indexed_at, COUNT(c.chunk_id) AS chunk_count
            FROM documents d
            LEFT JOIN chunks c ON c.document_id = d.document_id
            WHERE d.document_id = ?
            GROUP BY d.document_id
            """,
            (document_id.value,),
        ).fetchone()
        return None if row is None else _state_from_row(row)

    @wrap_driver_errors
    def list_states(self) -> Sequence[DocumentState]:
        rows = self._connection.execute(
            """
            SELECT
                d.document_id, d.relative_path, d.revision, d.content_hash,
                d.modified_at, d.indexed_at, COUNT(c.chunk_id) AS chunk_count
            FROM documents d
            LEFT JOIN chunks c ON c.document_id = d.document_id
            GROUP BY d.document_id
            ORDER BY d.relative_path
            """
        ).fetchall()
        return tuple(_state_from_row(row) for row in rows)

    @wrap_driver_errors
    def list_relative_paths(self) -> Sequence[RelativePath]:
        rows = self._connection.execute(
            "SELECT relative_path FROM documents ORDER BY relative_path"
        ).fetchall()
        return tuple(RelativePath(row["relative_path"]) for row in rows)

    @wrap_driver_errors
    def save_indexed(
        self,
        document: Document,
        chunks: Sequence[Chunk],
        indexed_at: datetime,
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO documents (
                document_id, relative_path, revision, content_hash, modified_at, indexed_at
            ) VALUES (
                :document_id, :relative_path, :revision, :content_hash, :modified_at, :indexed_at
            )
            ON CONFLICT (document_id) DO UPDATE SET
                relative_path = excluded.relative_path,
                revision = excluded.revision,
                content_hash = excluded.content_hash,
                modified_at = excluded.modified_at,
                indexed_at = excluded.indexed_at
            """,
            {
                "document_id": document.id.value,
                "relative_path": document.relative_path.value,
                "revision": document.revision,
                "content_hash": document.content_hash,
                "modified_at": document.modified_at.isoformat(),
                "indexed_at": indexed_at.isoformat(),
            },
        )
        self._connection.execute("DELETE FROM chunks WHERE document_id = ?", (document.id.value,))
        self._connection.executemany(
            """
            INSERT INTO chunks (
                chunk_id, document_id, chunk_index, heading_path,
                char_start, char_end, token_count, content_hash,
                heading_line, heading_occurrence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    chunk.id.value,
                    document.id.value,
                    chunk.chunk_index,
                    json.dumps(list(chunk.heading_path), ensure_ascii=False),
                    chunk.char_range.start,
                    chunk.char_range.end,
                    chunk.token_count,
                    chunk.content_hash,
                    chunk.heading_line,
                    chunk.heading_occurrence,
                )
                for chunk in chunks
            ],
        )

    @wrap_driver_errors
    def update_path(
        self,
        document_id: DocumentId,
        relative_path: RelativePath,
    ) -> None:
        self._connection.execute(
            "UPDATE documents SET relative_path = ? WHERE document_id = ?",
            (relative_path.value, document_id.value),
        )

    @wrap_driver_errors
    def delete(self, document_id: DocumentId) -> None:
        self._connection.execute(
            "DELETE FROM documents WHERE document_id = ?", (document_id.value,)
        )


def _state_from_row(row: sqlite3.Row) -> DocumentState:
    return DocumentState(
        document_id=DocumentId(row["document_id"]),
        relative_path=RelativePath(row["relative_path"]),
        revision=row["revision"],
        content_hash=row["content_hash"],
        modified_at=datetime.fromisoformat(row["modified_at"]),
        indexed_at=datetime.fromisoformat(row["indexed_at"]),
        chunk_count=row["chunk_count"],
    )
