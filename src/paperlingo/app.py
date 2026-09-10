"""应用启动：HiDPI、字体、主题、数据库、主窗口。"""

from __future__ import annotations

import logging
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from paperlingo.database.db import Database
from paperlingo.database.repository import Repository
from paperlingo.services.logging_setup import setup_logging
from paperlingo.services.settings import AppSettings
from paperlingo.ui.main_window import MainWindow
from paperlingo.ui.theme import build_qss, palette

logger = logging.getLogger(__name__)


def _apply_scale_fonts(qss: str, scale: float) -> str:
    import re

    def repl(m: re.Match) -> str:
        return f"font-size: {max(9, round(int(m.group(1)) * scale))}px"

    return re.sub(r"font-size:\s*(\d+)px", repl, qss)


def run() -> int:
    log_file = setup_logging()
    logger.info("PaperLingo 启动，日志文件：%s", log_file)

    def _excepthook(exc_type, exc, tb) -> None:
        logger.critical("未捕获异常", exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _excepthook

    # 高 DPI：Qt6 默认启用，这里再做圆角策略
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("PaperLingo")
    app.setOrganizationName("PaperLingo")

    # 默认字体：Windows 上微软雅黑 UI 优先
    font = QFont("Microsoft YaHei UI", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    try:
        db = Database()
        repo = Repository(db)
    except Exception:
        logger.exception("数据库初始化失败：%s", "?")
        raise
    settings = AppSettings.load(repo)

    theme_key = settings.theme
    if theme_key == "system":
        from paperlingo.ui.theme import system_theme

        theme_key = system_theme()
    qss = build_qss(palette(theme_key))
    if abs(settings.font_scale - 1.0) > 1e-6:
        qss = _apply_scale_fonts(qss, settings.font_scale)
    app.setStyleSheet(qss)

    win = MainWindow(db, repo, settings)
    win.show()
    code = app.exec()
    db.close()
    return code
