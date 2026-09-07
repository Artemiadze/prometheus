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
from application.errors import IndexCorruptedError
from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import Document
from domain.entities.search_hit import SearchHit, sort_by_score
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath
from domain.value_objects.search_scope import ScopeMode, SearchScope

COLLECTION_NAME = "chunks"
_POINT_NAMESPACE = UUID("62e3cb19-e15a-4b15-9b46-ad8f84c3b8bc")
_INDEXED_PAYLOAD_FIELDS = ("folder", "folder_ancestors", "file_path", "document_id")


class QdrantLocalVectorIndex:
    """Store and search one Vault in an embedded Qdrant collection."""

    def __init__(
        self,
        *,
        vault_dir: Path,
        embedding_fingerprint: EmbeddingFingerprint,
        client_factory: Callable[[], QdrantClient] | None = None,
    ) -> None:
        self._vault_dir = vault_dir.expanduser().resolve()
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

    def upsert(
        self,
        document: Document,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        self._validate_upsert(document, chunks, vectors)
        self.delete_by_document(document.id)
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
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        if any(chunk.document_id != document.id for chunk in chunks):
            raise ValueError("all chunks must belong to document")
        dimension = self._expected_metadata.embedding.dimension
        if any(len(vector) != dimension for vector in vectors):
            raise ValueError("vector dimension does not match the collection")

    def delete_by_document(self, document_id: DocumentId) -> None:
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
                query_filter=self._scope_filter(scope),
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
            hits = tuple(self._to_search_hit(point) for point in response.points)
        except Exception as error:
            self._status = IndexStatus.CORRUPTED
            raise IndexCorruptedError() from error
        return sort_by_score(hits)[:limit]

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

    @staticmethod
    def _payload(document: Document, chunk: Chunk) -> dict[str, Any]:
        folder = document.relative_path.parent
        ancestors = _folder_ancestors(document.relative_path)
        return {
            "document_id": document.id.value,
            "file_path": document.relative_path.value,
            "folder": folder.value if folder is not None else "",
            "folder_ancestors": ancestors,
            "heading": chunk.heading,
            "heading_path": list(chunk.heading_path),
            "chunk_id": chunk.id.value,
            "chunk_index": chunk.chunk_index,
            "content": chunk.text,
            "content_hash": chunk.content_hash,
            "modified_at": document.modified_at.isoformat(),
            "char_range_start": chunk.char_range.start,
            "char_range_end": chunk.char_range.end,
            "token_count": chunk.token_count,
        }

    @staticmethod
    def _to_search_hit(point: models.ScoredPoint) -> SearchHit:
        payload = point.payload
        if payload is None:
            raise ValueError("Qdrant point has no payload")
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
    )
