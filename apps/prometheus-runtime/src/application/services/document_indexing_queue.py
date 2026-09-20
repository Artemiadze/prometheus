"""Serialize concurrent indexing for the same document (PRM-67)."""

from __future__ import annotations

import asyncio

from application.dto.indexing import IndexDocumentResult
from application.use_cases.index_document import IndexDocument
from domain.entities.document import Document
from domain.value_objects.document_id import DocumentId


class SerializedDocumentIndexing:
    """Ensure one in-flight index per document; skip stale revisions."""

    def __init__(self, index_document: IndexDocument) -> None:
        self._index = index_document
        self._locks: dict[DocumentId, asyncio.Lock] = {}
        self._latest_revision: dict[DocumentId, int] = {}
        self._pending: dict[DocumentId, Document] = {}
        self._indexed_revision: dict[DocumentId, int] = {}
        self._meta_lock = asyncio.Lock()

    async def execute(
        self,
        document: Document,
        *,
        force: bool = False,
    ) -> IndexDocumentResult:
        async with self._meta_lock:
            latest = self._latest_revision.get(document.id, -1)
            self._latest_revision[document.id] = max(latest, document.revision)
            pending = self._pending.get(document.id)
            if pending is None or document.revision >= pending.revision:
                self._pending[document.id] = document
            lock = self._locks.setdefault(document.id, asyncio.Lock())

        if document.revision < self._latest_revision[document.id]:
            return IndexDocumentResult(document.id, 0, 0, skipped=True)

        async with lock:
            await asyncio.sleep(0)
            while True:
                async with self._meta_lock:
                    target = self._pending[document.id]
                    latest_revision = self._latest_revision[document.id]
                    indexed_revision = self._indexed_revision.get(document.id, -1)
                if document.revision < latest_revision:
                    return IndexDocumentResult(document.id, 0, 0, skipped=True)
                if target.revision < latest_revision:
                    await asyncio.sleep(0)
                    continue
                if indexed_revision >= target.revision:
                    return IndexDocumentResult(document.id, 0, 0, skipped=True)
                result = await self._index.execute(target, force=force)
                async with self._meta_lock:
                    self._indexed_revision[document.id] = target.revision
                    if self._pending[document.id].revision > target.revision:
                        continue
                return result
