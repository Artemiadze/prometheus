"""Cooperative cancellation application port."""

from typing import Protocol


class CancellationToken(Protocol):
    """Expose cancellation without coupling use cases to a job runner."""

    def is_cancelled(self) -> bool: ...
