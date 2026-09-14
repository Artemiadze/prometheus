"""SQLite transaction boundary for the metadata database."""

from __future__ import annotations

import sqlite3
from types import TracebackType
from typing import Literal


class SqliteUnitOfWork:
    """Wrap one ``BEGIN``/``COMMIT``/``ROLLBACK`` cycle on a shared connection.

    Mirrors :class:`FakeUnitOfWork`'s semantics: entering starts a transaction,
    exiting without an explicit :meth:`commit` (or exiting because of an exception)
    rolls it back. The instance is safe to reuse for successive transactions.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._committed = False

    def __enter__(self) -> SqliteUnitOfWork:
        self._committed = False
        self._connection.execute("BEGIN")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        if exc_type is not None or not self._committed:
            self.rollback()
        return False

    def commit(self) -> None:
        self._connection.execute("COMMIT")
        self._committed = True

    def rollback(self) -> None:
        self._connection.execute("ROLLBACK")
