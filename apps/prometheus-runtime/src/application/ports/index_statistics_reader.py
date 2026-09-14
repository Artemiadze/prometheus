"""Index statistics application port."""

from typing import Protocol

from application.dto.statistics import IndexStatistics


class IndexStatisticsReader(Protocol):
    """Report aggregate index counters without touching the vector store."""

    def read(self) -> IndexStatistics: ...
