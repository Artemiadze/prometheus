"""SQLite FTS5 BM25 lexical index over chunk text."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Sequence

from adapters.outbound.sqlite.errors import LexicalIndexUnavailableError, wrap_driver_errors
from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import Document
from domain.entities.search_hit import SearchHit, sort_by_score
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath
from domain.value_objects.search_scope import ScopeMode, SearchScope

_TOKEN_SPLIT = re.compile(r"\s+")
_PUNCT_GAP = re.compile(r"([\-_/]+)")


def split_friendly_content(text: str) -> str:
    """Insert gaps around punctuation clusters so split-friendly tokens match partial queries."""

    return _PUNCT_GAP.sub(r" \1 ", text)


def escape_fts_token(token: str) -> str:
    return token.replace('"', '""')


def build_fts_match_query(query: str) -> str | None:
    """Build a safe OR-joined phrase query; user FTS operators are not interpreted."""

    tokens: list[str] = []
    for part in _TOKEN_SPLIT.split(query.strip()):
        if not part:
            continue
        cleaned = part.strip('"')
        if cleaned:
            tokens.append(cleaned)
    if not tokens:
        return None
    return " OR ".join(f'"{escape_fts_token(token)}"' for token in tokens)


def folder_value(relative_path: RelativePath) -> str:
    parent = relative_path.parent
    return parent.value if parent is not None else ""


class SqliteLexicalIndex:
    """Persist and search chunk text with FTS5 BM25 ranking."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @wrap_driver_errors
    def replace_document(self, document: Document, chunks: Sequence[Chunk]) -> None:
        self.delete_by_document(document.id)
        if not chunks:
            return
        folder = folder_value(document.relative_path)
        self._connection.executemany(
            """
            INSERT INTO chunks_fts (
                content, content_split, chunk_id, document_id, file_path, folder
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    chunk.text,
                    split_friendly_content(chunk.text),
                    chunk.id.value,
                    document.id.value,
                    document.relative_path.value,
                    folder,
                )
                for chunk in chunks
            ],
        )

    @wrap_driver_errors
    def delete_by_document(self, document_id: DocumentId) -> None:
        self._connection.execute(
            "DELETE FROM chunks_fts WHERE document_id = ?",
            (document_id.value,),
        )

    @wrap_driver_errors
    def update_document_path(
        self,
        document_id: DocumentId,
        relative_path: RelativePath,
    ) -> None:
        self._connection.execute(
            """
            UPDATE chunks_fts
            SET file_path = ?, folder = ?
            WHERE document_id = ?
            """,
            (relative_path.value, folder_value(relative_path), document_id.value),
        )

    @wrap_driver_errors
    def search(
        self,
        query: str,
        limit: int,
        scope: SearchScope | None = None,
    ) -> Sequence[SearchHit]:
        if limit < 0:
            raise ValueError("limit cannot be negative")
        if limit == 0:
            return ()
        match_query = build_fts_match_query(query)
        if match_query is None:
            return ()

        scope_sql, scope_params = _scope_clause(scope)
        sql = f"""
            SELECT
                chunks_fts.chunk_id,
                chunks_fts.content,
                c.document_id,
                c.chunk_index,
                c.heading_path,
                c.char_start,
                c.char_end,
                c.token_count,
                c.content_hash,
                c.heading_line,
                c.heading_occurrence,
                bm25(chunks_fts, 1.0, 0.5) AS rank
            FROM chunks_fts
            INNER JOIN chunks AS c ON c.chunk_id = chunks_fts.chunk_id
            WHERE chunks_fts MATCH ?
              {scope_sql}
            ORDER BY rank ASC
            LIMIT ?
        """
        params: list[object] = [match_query, *scope_params, limit]
        rows = self._connection.execute(sql, params).fetchall()
        hits: list[SearchHit] = []
        for row in rows:
            heading_path_value = json.loads(row["heading_path"])
            if not isinstance(heading_path_value, list):
                raise ValueError("invalid heading_path in chunks table")
            chunk = Chunk(
                id=ChunkId(row["chunk_id"]),
                document_id=DocumentId(row["document_id"]),
                text=row["content"],
                heading_path=tuple(str(item) for item in heading_path_value),
                chunk_index=row["chunk_index"],
                char_range=CharRange(row["char_start"], row["char_end"]),
                token_count=row["token_count"],
                content_hash=row["content_hash"],
                heading_line=row["heading_line"],
                heading_occurrence=row["heading_occurrence"],
            )
            lexical_score = float(-row["rank"])
            hits.append(
                SearchHit(
                    chunk=chunk,
                    score=lexical_score,
                    lexical_score=lexical_score,
                )
            )
        return sort_by_score(hits)[:limit]


def _scope_clause(scope: SearchScope | None) -> tuple[str, list[str]]:
    excluded_sql, excluded_params = _excluded_folders_clause(scope)
    if scope is None or scope.mode is ScopeMode.ENTIRE_VAULT:
        return excluded_sql, excluded_params
    if scope.mode is ScopeMode.CURRENT_NOTE:
        assert scope.note is not None
        return f"AND chunks_fts.file_path = ? {excluded_sql}", [scope.note.value, *excluded_params]
    folders = scope.folders
    if scope.mode is ScopeMode.CURRENT_FOLDER:
        assert len(folders) == 1
        folders = (folders[0],)
    clauses: list[str] = []
    params: list[str] = []
    for folder in folders:
        prefix = folder.value
        clauses.append(
            "(chunks_fts.folder = ? OR chunks_fts.file_path = ? OR chunks_fts.file_path LIKE ?)"
        )
        params.extend([prefix, prefix, f"{prefix}/%"])
    return f"AND ({' OR '.join(clauses)}) {excluded_sql}", [*params, *excluded_params]


def _excluded_folders_clause(scope: SearchScope | None) -> tuple[str, list[str]]:
    if scope is None or not scope.excluded_folders:
        return "", []
    clauses: list[str] = []
    params: list[str] = []
    for folder in scope.excluded_folders:
        prefix = folder.value
        clauses.append(
            "NOT (chunks_fts.folder = ? OR chunks_fts.file_path = ? OR chunks_fts.file_path LIKE ?)"
        )
        params.extend([prefix, prefix, f"{prefix}/%"])
    if not clauses:
        return "", []
    return f"AND {' AND '.join(clauses)}", params


def ensure_fts5_available(connection: sqlite3.Connection) -> None:
    """Verify FTS5 is available before applying the lexical migration."""

    try:
        connection.execute("CREATE VIRTUAL TABLE IF NOT EXISTS __fts5_probe USING fts5(content)")
        connection.execute("DROP TABLE IF EXISTS __fts5_probe")
    except sqlite3.OperationalError as error:
        raise LexicalIndexUnavailableError() from error
