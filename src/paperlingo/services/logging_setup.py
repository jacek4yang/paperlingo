"""轻量日志：写入用户数据目录 logs/paperlingo.log（Windows: %LOCALAPPDATA%/PaperLingo/logs）。

只记录关键错误（启动 / 数据库 / 解析 / ingest / 导出），不记录论文正文。
标准库实现，按大小滚动（5 个文件 × 1MB）。
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from paperlingo.database.db import default_data_dir

_LOG_FILENAME = "paperlingo.log"
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 5

_configured = False


def logs_dir() -> Path:
    return default_data_dir() / "logs"


def setup_logging(level: int = logging.INFO) -> Path:
    """初始化根 logger。返回日志文件路径（供开发定位）。"""
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
