"""Private-file sqlite3 connection factory with WAL and safety pragmas."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def open_connection(path: Path) -> sqlite3.Connection:
    """Open (creating if needed) a private, WAL-mode connection to ``path``.

    The connection uses ``isolation_level=None`` (driver autocommit) so callers get
    full control over transaction boundaries with explicit ``BEGIN``/``COMMIT``/
    ``ROLLBACK`` statements, as used by :class:`SqliteUnitOfWork`.
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
    return connection
