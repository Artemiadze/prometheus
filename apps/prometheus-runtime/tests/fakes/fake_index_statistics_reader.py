"""In-memory IndexStatisticsReader for unit tests."""

from __future__ import annotations

from application.dto.statistics import IndexStatistics


class FakeIndexStatisticsReader:
    """Return a fixed, test-provided statistics snapshot."""

    def __init__(self, statistics: IndexStatistics | None = None) -> None:
        self._statistics = statistics or IndexStatistics(
            document_count=0, chunk_count=0, last_indexed_at=None, index_size_bytes=0
        )

    def read(self) -> IndexStatistics:
        return self._statistics
