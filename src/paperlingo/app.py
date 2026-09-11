"""Application startup: HiDPI, fonts, theme, database, main window."""

from __future__ import annotations

import logging
import re
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QMessageBox

from paperlingo.database.db import Database, DatabaseOpenError
from paperlingo.database.repository import Repository
from paperlingo.services.logging_setup import setup_logging
from paperlingo.services.settings import AppSettings
from paperlingo.ui.main_window import MainWindow
from paperlingo.ui.theme import build_qss, palette

logger = logging.getLogger(__name__)


def _apply_scale_fonts(qss: str, scale: float) -> str:
    def repl(m: re.Match) -> str:
        return f"font-size: {max(9, round(int(m.group(1)) * scale))}px"

    return re.sub(r"font-size:\s*(\d+)px", repl, qss)


def _report_database_error(path, reason: str) -> None:
    """Show a clear, user-facing Chinese error for an unopenable database and
    terminate cleanly. This is the portable-app contract: never silently fall
    back to another location."""
    message = (
        "无法创建或打开本地数据库：\n\n"
        f"{path}\n\n"
        "PaperLingo 是免安装应用，数据保存在程序所在目录。请把程序放到一个可写的目录"
        "（例如桌面或文档文件夹）后重新启动。\n\n"
        f"错误详情：{reason}"
    )
    logger.critical("database initialization failed at %s: %s", path, reason)
    try:
        box = QMessageBox(QMessageBox.Icon.Critical, "PaperLingo", message)
        box.exec()
    except Exception:
        # No QApplication possible — fall back to stderr.
        print(message, file=sys.stderr)


def run() -> int:
    log_file = setup_logging()
    logger.info("PaperLingo starting, log file: %s", log_file)

    def _excepthook(exc_type, exc, tb) -> None:
        logger.critical("uncaught exception", exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _excepthook

    # HiDPI: on by default in Qt6; configure the rounding policy here.
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("PaperLingo")
    app.setOrganizationName("PaperLingo")

    # Default font: prefer Microsoft YaHei UI on Windows.
    font = QFont("Microsoft YaHei UI", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    try:
        db = Database()
        repo = Repository(db)
    except DatabaseOpenError as e:
        _report_database_error(e.path, e.reason)
        return 1
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
    # Shutdown safety net: close on aboutToQuit AND in a finally block so a
    # crashed event loop still commits/checkpoints/closes the database.
    app.aboutToQuit.connect(db.close)
    try:
        return app.exec()
    finally:
        db.close()
