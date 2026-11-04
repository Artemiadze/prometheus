"""Vault-scoped dense vector index backed by sqlite-vec inside metadata.sqlite."""

from __future__ import annotations

import contextlib
import json
import re
import sqlite3
import struct
from collections.abc import Mapping, Sequence

from application.dto.embedding import EmbeddingFingerprint
from application.dto.index_status import IndexStatus
from application.errors import IndexCorruptedError, VaultMismatchError
from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import Document
from domain.entities.search_hit import SearchHit, sort_by_score
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath
from domain.value_objects.search_scope import ScopeMode, SearchScope
from domain.value_objects.vault_id import VaultId

VECTOR_TABLE = "chunk_vectors"
_FLOAT_DIM_RE = re.compile(r"float\[(\d+)\]", re.IGNORECASE)


class SqliteVecVectorIndex:
    """Store and search one Vault's embeddings in a sqlite-vec ``vec0`` table."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        vault_id: VaultId,
        embedding_fingerprint: EmbeddingFingerprint,
    ) -> None:
        self._connection = connection
        self._vault_id = vault_id
        self._fingerprint = embedding_fingerprint
        self._status = IndexStatus.READY
        self._initialize()

    @property
    def status(self) -> IndexStatus:
        return self._status

    def _initialize(self) -> None:
        try:
            existing_dim = self._existing_dimension()
            if existing_dim is None:
                self._create_vector_table()
                return
            if existing_dim != self._fingerprint.dimension:
                self._drop_vector_table()
                self._create_vector_table()
                self._status = IndexStatus.CORRUPTED
        except Exception:
            self._recover_from_corruption()

    def _recover_from_corruption(self) -> None:
        self._status = IndexStatus.CORRUPTED
        with contextlib.suppress(Exception):
            self._drop_vector_table()
            self._create_vector_table()

    def _existing_dimension(self) -> int | None:
        row = self._connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (VECTOR_TABLE,),
        ).fetchone()
        if row is None or row["sql"] is None:
            return None
        match = _FLOAT_DIM_RE.search(str(row["sql"]))
        return int(match.group(1)) if match else None

    def _create_vector_table(self) -> None:
        dimension = self._fingerprint.dimension
        self._connection.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS {VECTOR_TABLE} USING vec0(
                chunk_id TEXT PRIMARY KEY,
                embedding float[{dimension}] distance_metric=cosine
            )
            """
        )

    def _drop_vector_table(self) -> None:
        self._connection.execute(f"DROP TABLE IF EXISTS {VECTOR_TABLE}")

    def retrieve_vectors(self, chunk_ids: Sequence[ChunkId]) -> Mapping[str, Sequence[float]]:
        if not chunk_ids:
            return {}
        placeholders = ", ".join("?" for _ in chunk_ids)
        rows = self._connection.execute(
            f"""
            SELECT chunk_id, embedding
            FROM {VECTOR_TABLE}
            WHERE chunk_id IN ({placeholders})
            """,
            tuple(chunk_id.value for chunk_id in chunk_ids),
        ).fetchall()
        dimension = self._fingerprint.dimension
        result: dict[str, Sequence[float]] = {}
        for row in rows:
            blob = row["embedding"]
            if not isinstance(blob, (bytes, memoryview)):
                continue
            raw = bytes(blob)
            if len(raw) != dimension * 4:
                continue
            result[str(row["chunk_id"])] = struct.unpack(f"<{dimension}f", raw)
        return result

    def upsert(
        self,
        document: Document,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        self._validate_upsert(document, chunks, vectors)
        # vec0 does not support INSERT OR REPLACE; delete then insert.
        self.delete_by_ids(tuple(chunk.id for chunk in chunks))
        for chunk, vector in zip(chunks, vectors, strict=True):
            payload = json.dumps([float(value) for value in vector])
            self._connection.execute(
                f"""
                INSERT INTO {VECTOR_TABLE} (chunk_id, embedding)
                VALUES (?, ?)
                """,
                (chunk.id.value, payload),
            )
        self._status = IndexStatus.READY

    def _validate_upsert(
        self,
        document: Document,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        if document.vault_id != self._vault_id:
            raise VaultMismatchError()
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        if any(chunk.document_id != document.id for chunk in chunks):
            raise ValueError("all chunks must belong to document")
        dimension = self._fingerprint.dimension
        if any(len(vector) != dimension for vector in vectors):
            raise ValueError("vector dimension does not match the collection")

    def delete_by_ids(self, chunk_ids: Sequence[ChunkId]) -> None:
        if not chunk_ids:
            return
        self._connection.executemany(
            f"DELETE FROM {VECTOR_TABLE} WHERE chunk_id = ?",
            [(chunk_id.value,) for chunk_id in chunk_ids],
        )

    def delete_by_document(self, document_id: DocumentId) -> None:
        self._connection.execute(
            f"""
            DELETE FROM {VECTOR_TABLE}
            WHERE chunk_id IN (
                SELECT chunk_id FROM chunks WHERE document_id = ?
            )
            """,
            (document_id.value,),
        )

    def update_document_path(
        self,
        document_id: DocumentId,
        relative_path: RelativePath,
    ) -> None:
        """No-op for vectors: path and ancestors live in the relational manifest."""

        del document_id, relative_path

    def search(
        self,
        query_vector: Sequence[float],
        limit: int,
        scope: SearchScope | None = None,
    ) -> Sequence[SearchHit]:
        if limit < 0:
            raise ValueError("limit cannot be negative")
        if self._status is IndexStatus.CORRUPTED:
            raise IndexCorruptedError()
        if len(query_vector) != self._fingerprint.dimension:
            raise ValueError("query vector dimension does not match the collection")
        if limit == 0:
            return ()
        try:
            sql, params = self._search_sql(scope, limit)
            query_json = json.dumps([float(value) for value in query_vector])
            rows = self._connection.execute(sql, (query_json, *params)).fetchall()
            hits = tuple(self._row_to_search_hit(row) for row in rows)
        except IndexCorruptedError:
            raise
        except Exception as error:
            self._status = IndexStatus.CORRUPTED
            raise IndexCorruptedError() from error
        return sort_by_score(hits)[:limit]

    def _search_sql(self, scope: SearchScope | None, limit: int) -> tuple[str, list[object]]:
        filters: list[str] = []
        params: list[object] = [limit]
        if scope is not None and scope.mode is ScopeMode.CURRENT_NOTE:
            assert scope.note is not None
            filters.append("d.relative_path = ?")
            params.append(scope.note.value)
        elif scope is not None and scope.mode is not ScopeMode.ENTIRE_VAULT:
            folders = [folder.value for folder in scope.folders]
            if not folders:
                filters.append("1 = 0")
            else:
                placeholders = ", ".join("?" for _ in folders)
                filters.append(
                    f"""
                    EXISTS (
                        SELECT 1 FROM chunk_folder_ancestors a
                        WHERE a.chunk_id = c.chunk_id AND a.folder IN ({placeholders})
                    )
                    """
                )
                params.extend(folders)
        if scope is not None and scope.excluded_folders:
            excluded = [folder.value for folder in scope.excluded_folders]
            placeholders = ", ".join("?" for _ in excluded)
            filters.append(
                f"""
                NOT EXISTS (
                    SELECT 1 FROM chunk_folder_ancestors a
                    WHERE a.chunk_id = c.chunk_id AND a.folder IN ({placeholders})
                )
                """
            )
            params.extend(excluded)

        where_extra = ""
        if filters:
            where_extra = " AND " + " AND ".join(filters)

        sql = f"""
            SELECT
                c.chunk_id,
                c.document_id,
                c.content,
                c.heading_path,
                c.chunk_index,
                c.char_start,
                c.char_end,
                c.token_count,
                c.content_hash,
                c.heading_line,
                c.heading_occurrence,
                v.distance
            FROM {VECTOR_TABLE} AS v
            JOIN chunks AS c ON c.chunk_id = v.chunk_id
            JOIN documents AS d ON d.document_id = c.document_id
            WHERE v.embedding MATCH ?
              AND k = ?
              {where_extra}
            ORDER BY v.distance
        """
        return sql, params

    def _row_to_search_hit(self, row: sqlite3.Row) -> SearchHit:
        heading_path_raw = json.loads(row["heading_path"])
        if not isinstance(heading_path_raw, list) or not all(
            isinstance(item, str) for item in heading_path_raw
        ):
            raise ValueError("invalid heading_path")
        chunk = Chunk(
            id=ChunkId(str(row["chunk_id"])),
            document_id=DocumentId(str(row["document_id"])),
            text=str(row["content"] or ""),
            heading_path=tuple(heading_path_raw),
            chunk_index=int(row["chunk_index"]),
            char_range=CharRange(int(row["char_start"]), int(row["char_end"])),
            token_count=int(row["token_count"]),
            content_hash=str(row["content_hash"]),
            heading_line=row["heading_line"],
            heading_occurrence=row["heading_occurrence"],
        )
        # sqlite-vec cosine distance is 1 - cosine_similarity; SearchHit wants higher=better.
        score = 1.0 - float(row["distance"])
        return SearchHit(chunk=chunk, score=score, dense_score=score)

    def close(self) -> None:
        """No-op: connection lifetime is owned by MetadataDatabase."""
