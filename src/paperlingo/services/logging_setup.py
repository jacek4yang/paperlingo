"""Lightweight logging: writes to logs/paperlingo.log inside the application
data directory (beside the exe when packaged, project root in development).

Records key errors only (startup / database / parsing / ingest / export); never
paper content. Standard-library implementation, size-rotated (5 files x 1MB).
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from paperlingo.database.db import application_data_dir

_LOG_FILENAME = "paperlingo.log"
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 5

_configured = False


def logs_dir() -> Path:
    return application_data_dir() / "logs"


def setup_logging(level: int = logging.INFO) -> Path:
    """Initialize the root logger. Returns the log file path (for development)."""
    global _configured
    log_file = logs_dir() / _LOG_FILENAME
    if _configured:
        return log_file
    try:
        logs_dir().mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
        )
    except OSError:
        handler = logging.NullHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)
    _configured = True
    return log_file
