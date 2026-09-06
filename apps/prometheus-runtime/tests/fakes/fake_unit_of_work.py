"""State-recording UnitOfWork fake."""

from __future__ import annotations

from types import TracebackType
from typing import Literal


class FakeUnitOfWork:
    """Record transaction decisions without persistence."""

    def __init__(self) -> None:
        self.entered = False
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> FakeUnitOfWork:
        self.entered = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        if exc_type is not None or not self.committed:
            self.rollback()
        return False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True
