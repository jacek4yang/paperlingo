"""SQLite connection management.

The database is a portable, side-by-side asset: packaged, it lives next to
PaperLingo.exe; in development, it lives at a deterministic project-local path.
This portable contract intentionally replaces the previous AppData behavior.
"""

from __future__ import annotations

import logging
import sqlite3
import sys
from pathlib import Path

from paperlingo.database.migrations import CURRENT_DB_VERSION, migrate

logger = logging.getLogger(__name__)

APP_NAME = "PaperLingo"
DB_FILENAME = "paperlingo.db"

_BUSY_TIMEOUT_MS = 5000


class DatabaseOpenError(RuntimeError):
    """Raised when the database cannot be created/opened at its portable path.

    Carries the path so the UI can show a clear, localized error including it.
    """

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"cannot open database at {path}: {reason}")
        self.path = path
        self.reason = reason


def application_data_dir() -> Path:
    """Directory holding the application's portable data (database, logs).

    Invariant: packaged app -> directory containing the executable;
    development -> the repository root (project-local, deterministic).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # src/paperlingo/database/db.py -> parents[3] is the repository root.
    return Path(__file__).resolve().parents[3]


def default_db_path() -> Path:
    return application_data_dir() / DB_FILENAME


class Database:
    """Owns the SQLite connection, runs migrations. All queries are parameterized."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else default_db_path()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # isolation_level=None -> autocommit mode: every transaction in the
            # repository layer is explicit (BEGIN IMMEDIATE / COMMIT / ROLLBACK).
            self._conn = sqlite3.connect(
                str(self.path), check_same_thread=False, isolation_level=None
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
            # WAL + NORMAL is a strong, standard durability profile for a small
            # desktop application (see AGENTS.md database contract).
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA synchronous = NORMAL")
            migrate(self._conn)
        except (sqlite3.Error, OSError) as e:
            # Surface a hard, explicit failure (e.g. exe directory not writable)
            # instead of silently falling back to another location.
            raise DatabaseOpenError(self.path, str(e)) from e

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("database connection is closed")
        return self._conn

    def version(self) -> int:
        return int(self._conn.execute("PRAGMA user_version").fetchone()[0])

    def is_current(self) -> bool:
        return self.version() == CURRENT_DB_VERSION

    def close(self) -> None:
        """Close the database. Idempotent: safe to call more than once.

        Commits pending work, runs PRAGMA optimize, checkpoints the WAL, closes
        the connection, and clears the internal reference.
        """
        if self._conn is None:
            return
        conn, self._conn = self._conn, None
        try:
            conn.commit()
            conn.execute("PRAGMA optimize")
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error:
            logger.warning("error during database shutdown checkpoint", exc_info=True)
        finally:
            try:
                conn.close()
            except sqlite3.Error:
                logger.warning("error closing database connection", exc_info=True)

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
