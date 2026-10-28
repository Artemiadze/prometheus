"""Vault-scoped vector index backed by persistent Qdrant Local storage."""

from __future__ import annotations

import shutil
import warnings
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from qdrant_client import QdrantClient, models

from adapters.outbound.qdrant.index_metadata import (
    IndexMetadata,
    read_index_metadata,
    write_index_metadata,
)
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

COLLECTION_NAME = "chunks"
_POINT_NAMESPACE = UUID("62e3cb19-e15a-4b15-9b46-ad8f84c3b8bc")
_INDEXED_PAYLOAD_FIELDS = ("vault_id", "folder", "folder_ancestors", "file_path", "document_id")


class QdrantLocalVectorIndex:
    """Store and search one Vault in an embedded Qdrant collection."""

    def __init__(
        self,
        *,
        vault_dir: Path,
        vault_id: VaultId,
        embedding_fingerprint: EmbeddingFingerprint,
        client_factory: Callable[[], QdrantClient] | None = None,
    ) -> None:
        self._vault_dir = vault_dir.expanduser().resolve()
        self._vault_id = vault_id
        self._storage_dir = self._vault_dir / "qdrant"
        self._metadata_path = self._vault_dir / "qdrant_metadata.json"
        self._expected_metadata = IndexMetadata(embedding_fingerprint)
        self._owns_storage = client_factory is None
        self._client_factory = client_factory or self._build_local_client
        self._client: QdrantClient | None = None
        self._status = IndexStatus.READY
        self._initialize()

    @property
    def status(self) -> IndexStatus:
        return self._status

    def _build_local_client(self) -> QdrantClient:
        self._storage_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        return QdrantClient(path=str(self._storage_dir))

    def _initialize(self) -> None:
        try:
            stored_metadata = read_index_metadata(self._metadata_path)
            self._client = self._client_factory()
            collection_exists = self._client.collection_exists(COLLECTION_NAME)
            if stored_metadata is None and not collection_exists:
                self._create_collection()
                self._write_metadata()
                return
            if (
                stored_metadata != self._expected_metadata
                or not collection_exists
                or not self._collection_is_compatible()
            ):
                self._recreate_collection()
                self._status = IndexStatus.CORRUPTED
                return
            self._ensure_payload_indexes()
        except Exception:
            self._recover_from_corruption()

    def _recover_from_corruption(self) -> None:
        self._status = IndexStatus.CORRUPTED
        self.close()
        if self._owns_storage:
            shutil.rmtree(self._storage_dir, ignore_errors=True)
        try:
            self._client = self._client_factory()
            self._recreate_collection()
        except Exception:
            self._client = None

    def _collection_is_compatible(self) -> bool:
        client = self._require_client()
        vectors = client.get_collection(COLLECTION_NAME).config.params.vectors
        return (
            isinstance(vectors, models.VectorParams)
            and vectors.size == self._expected_metadata.embedding.dimension
            and vectors.distance == models.Distance.COSINE
        )

    def _create_collection(self) -> None:
        self._require_client().create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=self._expected_metadata.embedding.dimension,
                distance=models.Distance.COSINE,
            ),
        )
        self._ensure_payload_indexes()

    def _recreate_collection(self) -> None:
        client = self._require_client()
        if client.collection_exists(COLLECTION_NAME):
            client.delete_collection(COLLECTION_NAME)
        self._create_collection()
        self._write_metadata()

    def _ensure_payload_indexes(self) -> None:
        client = self._require_client()
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Payload indexes have no effect in the local Qdrant.*",
                category=UserWarning,
            )
            for field in _INDEXED_PAYLOAD_FIELDS:
                client.create_payload_index(
                    collection_name=COLLECTION_NAME,
                    field_name=field,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )

    def _write_metadata(self) -> None:
        write_index_metadata(self._metadata_path, self._expected_metadata)

    def retrieve_vectors(self, chunk_ids: Sequence[ChunkId]) -> Mapping[str, Sequence[float]]:
        if not chunk_ids:
            return {}
        point_ids = [str(uuid5(_POINT_NAMESPACE, chunk_id.value)) for chunk_id in chunk_ids]
        records = self._require_client().retrieve(
            collection_name=COLLECTION_NAME,
            ids=point_ids,
            with_vectors=True,
        )
        vectors: dict[str, Sequence[float]] = {}
        for record in records:
            if record.vector is None:
                continue
            payload = record.payload or {}
            chunk_id = payload.get("chunk_id")
            if isinstance(chunk_id, str) and isinstance(record.vector, list):
                vectors[chunk_id] = [
                    float(value) for value in record.vector if isinstance(value, (int, float))
                ]
        return vectors

    def upsert(
        self,
        document: Document,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        """Insert or update the given points. Callers must delete stale chunk ids first."""

        self._validate_upsert(document, chunks, vectors)
        points = [
            models.PointStruct(
                id=str(uuid5(_POINT_NAMESPACE, chunk.id.value)),
                vector=[float(value) for value in vector],
                payload=self._payload(document, chunk),
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        if points:
            self._require_client().upsert(
                collection_name=COLLECTION_NAME,
                points=points,
                wait=True,
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
        dimension = self._expected_metadata.embedding.dimension
        if any(len(vector) != dimension for vector in vectors):
            raise ValueError("vector dimension does not match the collection")

    def delete_by_ids(self, chunk_ids: Sequence[ChunkId]) -> None:
        """Delete points by known chunk ids (O(k) in local Qdrant, no payload scan)."""

        if not chunk_ids:
            return
        point_ids: list[int | str | UUID] = [
            str(uuid5(_POINT_NAMESPACE, chunk_id.value)) for chunk_id in chunk_ids
        ]
        self._require_client().delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.PointIdsList(points=point_ids),
            wait=True,
        )

    def delete_by_document(self, document_id: DocumentId) -> None:
        """Fallback delete by payload filter; prefer ``delete_by_ids`` when ids are known."""

        self._require_client().delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id.value),
                    )
                ]
            ),
            wait=True,
        )

    def update_document_path(
        self,
        document_id: DocumentId,
        relative_path: RelativePath,
    ) -> None:
        folder = relative_path.parent
        self._require_client().set_payload(
            collection_name=COLLECTION_NAME,
            payload={
                "file_path": relative_path.value,
                "folder": folder.value if folder is not None else "",
                "folder_ancestors": _folder_ancestors(relative_path),
            },
            points=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id.value),
                    )
                ]
            ),
            wait=True,
        )

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
        if len(query_vector) != self._expected_metadata.embedding.dimension:
            raise ValueError("query vector dimension does not match the collection")
        if limit == 0:
            return ()
        try:
            response = self._require_client().query_points(
                collection_name=COLLECTION_NAME,
                query=[float(value) for value in query_vector],
                query_filter=self._search_filter(scope),
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
            hits = tuple(
                hit for point in response.points if (hit := self._to_search_hit(point)) is not None
            )
        except Exception as error:
            self._status = IndexStatus.CORRUPTED
            raise IndexCorruptedError() from error
        return sort_by_score(hits)[:limit]

    def _search_filter(self, scope: SearchScope | None) -> models.Filter:
        conditions: list[models.Condition] = [
            models.FieldCondition(
                key="vault_id",
                match=models.MatchValue(value=self._vault_id.value),
            )
        ]
        scope_filter = self._scope_filter(scope)
        if scope_filter is not None:
            extra = scope_filter.must
            if isinstance(extra, list):
                conditions.extend(extra)
            elif extra is not None:
                conditions.append(extra)
        must_not = self._excluded_folders_filter(scope)
        if must_not is not None:
            return models.Filter(must=conditions, must_not=must_not)
        return models.Filter(must=conditions)

    @staticmethod
    def _excluded_folders_filter(scope: SearchScope | None) -> list[models.Condition] | None:
        if scope is None or not scope.excluded_folders:
            return None
        values = [folder.value for folder in scope.excluded_folders]
        return [
            models.FieldCondition(
                key="folder_ancestors",
                match=models.MatchAny(any=values),
            )
        ]

    @staticmethod
    def _scope_filter(scope: SearchScope | None) -> models.Filter | None:
        if scope is None or scope.mode is ScopeMode.ENTIRE_VAULT:
            return None
        if scope.mode is ScopeMode.CURRENT_NOTE:
            assert scope.note is not None
            match: models.Match = models.MatchValue(value=scope.note.value)
            key = "file_path"
        else:
            match = models.MatchAny(any=[folder.value for folder in scope.folders])
            key = "folder_ancestors"
        return models.Filter(must=[models.FieldCondition(key=key, match=match)])

    def _payload(self, document: Document, chunk: Chunk) -> dict[str, Any]:
        folder = document.relative_path.parent
        ancestors = _folder_ancestors(document.relative_path)
        return {
            "vault_id": self._vault_id.value,
            "document_id": document.id.value,
            "file_path": document.relative_path.value,
            "folder": folder.value if folder is not None else "",
            "folder_ancestors": ancestors,
            "heading": chunk.heading,
            "heading_path": list(chunk.heading_path),
            "heading_line": chunk.heading_line,
            "heading_occurrence": chunk.heading_occurrence,
            "chunk_id": chunk.id.value,
            "chunk_index": chunk.chunk_index,
            "content": chunk.text,
            "content_hash": chunk.content_hash,
            "modified_at": document.modified_at.isoformat(),
            "char_range_start": chunk.char_range.start,
            "char_range_end": chunk.char_range.end,
            "token_count": chunk.token_count,
        }

    def _to_search_hit(self, point: models.ScoredPoint) -> SearchHit | None:
        payload = point.payload
        if payload is None:
            raise ValueError("Qdrant point has no payload")
        payload_vault = payload.get("vault_id")
        if payload_vault != self._vault_id.value:
            return None
        chunk = _chunk_from_payload(payload)
        score = float(point.score)
        return SearchHit(chunk=chunk, score=score, dense_score=score)

    def _require_client(self) -> QdrantClient:
        if self._client is None:
            raise IndexCorruptedError()
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


def _folder_ancestors(path: RelativePath) -> list[str]:
    ancestors: list[str] = []
    current = path.parent
    while current is not None:
        ancestors.append(current.value)
        current = current.parent
    return ancestors


def _required(payload: Mapping[str, Any], key: str, expected: type[Any]) -> Any:
    value = payload[key]
    if not isinstance(value, expected):
        raise ValueError(f"invalid payload field: {key}")
    return value


def _chunk_from_payload(payload: Mapping[str, Any]) -> Chunk:
    document_id = DocumentId(_required(payload, "document_id", str))
    heading_path_value = _required(payload, "heading_path", list)
    if not all(isinstance(heading, str) for heading in heading_path_value):
        raise ValueError("invalid payload field: heading_path")
    heading_line = payload.get("heading_line")
    heading_occurrence = payload.get("heading_occurrence")
    if heading_line is not None and not isinstance(heading_line, int):
        raise ValueError("invalid payload field: heading_line")
    if heading_occurrence is not None and not isinstance(heading_occurrence, int):
        raise ValueError("invalid payload field: heading_occurrence")
    return Chunk(
        id=ChunkId(_required(payload, "chunk_id", str)),
        document_id=document_id,
        text=_required(payload, "content", str),
        heading_path=tuple(heading_path_value),
        chunk_index=_required(payload, "chunk_index", int),
        char_range=CharRange(
            _required(payload, "char_range_start", int),
            _required(payload, "char_range_end", int),
        ),
        token_count=_required(payload, "token_count", int),
        content_hash=_required(payload, "content_hash", str),
        heading_line=heading_line,
        heading_occurrence=heading_occurrence,
    )
