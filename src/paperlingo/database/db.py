"""SQLite 连接管理。"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

from paperlingo.database.migrations import CURRENT_DB_VERSION, migrate

APP_NAME = "PaperLingo"
DB_FILENAME = "paperlingo.db"


def default_data_dir() -> Path:
    """用户数据目录：Windows 为 %LOCALAPPDATA%/PaperLingo（打包/开发一致）。"""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / APP_NAME
        return Path.home() / "AppData" / "Local" / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path.home() / ".local" / "share" / APP_NAME


def default_db_path() -> Path:
    return default_data_dir() / DB_FILENAME


class Database:
    """持有 SQLite 连接，执行迁移。所有查询用参数化语句。"""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        migrate(self._conn)

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def version(self) -> int:
        return self._conn.execute("PRAGMA user_version").fetchone()[0]

    def is_current(self) -> bool:
        return self.version() == CURRENT_DB_VERSION

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
