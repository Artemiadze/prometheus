"""Private-file sqlite3 connection factory with WAL, safety pragmas, and sqlite-vec."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import sqlite_vec  # type: ignore[import-untyped]

from adapters.outbound.sqlite.errors import VectorExtensionUnavailableError


def open_connection(path: Path) -> sqlite3.Connection:
    """Open (creating if needed) a private, WAL-mode connection to ``path``.

    The connection uses ``isolation_level=None`` (driver autocommit) so callers get
    full control over transaction boundaries with explicit ``BEGIN``/``COMMIT``/
    ``ROLLBACK`` statements, as used by :class:`SqliteUnitOfWork`.

    Loads the ``sqlite-vec`` extension required for dense vector search.
    """

    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    is_new_file = not path.exists()
    connection = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
    if is_new_file and os.name != "nt":
        path.chmod(0o600)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA synchronous = NORMAL")
    load_sqlite_vec(connection)
    return connection


def load_sqlite_vec(connection: sqlite3.Connection) -> None:
    """Load sqlite-vec into ``connection``; raise if the host SQLite cannot load extensions."""

    enable = getattr(connection, "enable_load_extension", None)
    if not callable(enable):
        raise VectorExtensionUnavailableError()
    try:
        connection.enable_load_extension(True)
        sqlite_vec.load(connection)
        connection.enable_load_extension(False)
    except (AttributeError, sqlite3.Error, OSError) as error:
        raise VectorExtensionUnavailableError() from error
