"""Build a resilient aggregate runtime status."""

from application.dto.index_fingerprint import IndexFingerprint
from application.dto.index_status import IndexStatus
from application.dto.runtime_status import IndexState, RuntimeStatus
from application.errors import IndexRebuildRequiredError
from application.ports.index_metadata_store import IndexMetadataStore
from application.ports.index_statistics_reader import IndexStatisticsReader
from application.ports.language_model import LanguageModel
from application.ports.vector_index import VectorIndex
from application.services.index_fingerprint import ensure_index_compatible


class GetRuntimeStatus:
    def __init__(
        self,
        *,
        runtime_version: str,
        llm_model: str,
        language_model: LanguageModel,
        vector_index: VectorIndex,
        index_metadata_store: IndexMetadataStore,
        index_statistics: IndexStatisticsReader,
        active_fingerprint: IndexFingerprint,
    ) -> None:
        self._runtime_version = runtime_version
        self._llm_model = llm_model
        self._llm = language_model
        self._vectors = vector_index
        self._metadata = index_metadata_store
        self._statistics = index_statistics
        self._fingerprint = active_fingerprint

    async def execute(self) -> RuntimeStatus:
        statistics = self._statistics.read()
        stored = self._metadata.load()
        index_state = self._index_state(stored, statistics.document_count)
        try:
            llm_available = await self._llm.is_available()
        except Exception:
            llm_available = False
        return RuntimeStatus(
            runtime_version=self._runtime_version,
            index_state=index_state,
            llm_available=llm_available,
            llm_model=self._llm_model,
            document_count=statistics.document_count,
            chunk_count=statistics.chunk_count,
            last_indexed_at=statistics.last_indexed_at,
            index_size_bytes=statistics.index_size_bytes,
        )

    def _index_state(
        self,
        stored: IndexFingerprint | None,
        document_count: int,
    ) -> IndexState:
        if stored is None or document_count == 0:
            return IndexState.NOT_INDEXED
        if self._vectors.status is IndexStatus.CORRUPTED:
            return IndexState.CORRUPTED
        try:
            ensure_index_compatible(stored, self._fingerprint)
        except IndexRebuildRequiredError:
            return IndexState.REBUILD_REQUIRED
        return IndexState.READY
