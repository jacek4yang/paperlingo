"""主窗口：左侧 Navigation Rail + 页面栈 + 主题管理。"""

from __future__ import annotations

from dataclasses import fields as dc_fields

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from paperlingo.database.db import Database
from paperlingo.database.repository import Repository
from paperlingo.services.settings import AppSettings
from paperlingo.ui.pages.history import HistoryPage
from paperlingo.ui.pages.knowledge import KnowledgePage
from paperlingo.ui.pages.reading import ReadingPage
from paperlingo.ui.pages.review import ReviewPage
from paperlingo.ui.theme import Palette, build_qss, palette, system_theme

APP_TITLE = "PaperLingo"


class MainWindow(QMainWindow):
    def __init__(self, db: Database, repo: Repository, settings: AppSettings) -> None:
        super().__init__()
        self.db = db
        self.repo = repo
        self.settings = settings
        self._theme_key = settings.theme

        self.setWindowTitle(APP_TITLE)
        self.resize(1280, 820)
        self.setMinimumSize(960, 640)

        # 共享的可变调色板（主题切换时原地更新）
        self.palette_obj = palette(self._effective_theme())

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        # ---------------- Navigation Rail ----------------
        rail = QFrame()
        rail.setFixedWidth(88)
        rail.setObjectName("navRail")
        rail_v = QVBoxLayout(rail)
        rail_v.setContentsMargins(8, 18, 8, 18)
        rail_v.setSpacing(4)

        logo = QLabel("PL")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("font-weight: 700; font-size: 16px; padding: 4px 0 10px 0;")
        rail_v.addWidget(logo)

        self._nav_buttons: dict[str, QPushButton] = {}
        for key, label in (
            ("reading", "阅读"),
            ("history", "历史"),
            ("knowledge", "知识"),
            ("review", "复习"),
        ):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                "text-align: center; padding: 10px 2px; border: none; border-radius: 10px;"
            )
            b.clicked.connect(lambda _=False, k=key: self.switch_page(k))
            rail_v.addWidget(b)
            self._nav_buttons[key] = b

        rail_v.addStretch(1)
        self._settings_btn = QPushButton("设置")
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.setStyleSheet(
            "text-align: center; padding: 10px 2px; border: none; border-radius: 10px;"
        )
        self._settings_btn.clicked.connect(self._open_settings)
        rail_v.addWidget(self._settings_btn)

        root.addWidget(rail)

        # ---------------- 页面栈 ----------------
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self.reading_page = ReadingPage(repo, self.palette_obj)
        self.history_page = HistoryPage(repo)
        self.knowledge_page = KnowledgePage(repo)
        self.review_page = ReviewPage(repo)
        for page in (
            self.reading_page, self.history_page,
            self.knowledge_page, self.review_page,
        ):
            self.stack.addWidget(page)

        # 信号
        self.history_page.restore_requested.connect(self._restore_analysis)
        self.history_page.reanalyze_requested.connect(self._reanalyze)
        self.reading_page.analysis_saved.connect(lambda _id: self._refresh_data_pages())

        self.switch_page("reading")

    # ------------------------------------------------------------------
    def _effective_theme(self) -> str:
        key = self.settings.theme
        return system_theme() if key == "system" else key

    def apply_theme(self, theme_key: str, font_scale: float = 1.0) -> None:
        """切换主题并重新应用 QSS；palette 对象原地更新。"""
        self._theme_key = theme_key
        effective = system_theme() if theme_key == "system" else theme_key
        new_p = palette(effective)
        for f in dc_fields(Palette):
            setattr(self.palette_obj, f.name, getattr(new_p, f.name))
        qss = build_qss(new_p)
        if abs(font_scale - 1.0) > 1e-6:
            qss = _scale_font_sizes(qss, font_scale)
        from PyQt6.QtWidgets import QApplication

        QApplication.instance().setStyleSheet(qss)

    def switch_page(self, key: str) -> None:
        pages = {
            "reading": (self.reading_page, 0),
            "history": (self.history_page, 1),
            "knowledge": (self.knowledge_page, 2),
            "review": (self.review_page, 3),
        }
        page, idx = pages[key]
        _ = page
        self.stack.setCurrentIndex(idx)
        for k, b in self._nav_buttons.items():
            b.setChecked(k == key)
        # 数据页进入时刷新
        if key == "history":
            self.history_page.refresh()
        elif key == "knowledge":
            self.knowledge_page.refresh()
        elif key == "review":
            self.review_page.refresh()

    # ------------------------------------------------------------------
    def _restore_analysis(self, analysis_id: int) -> None:
        loaded = self.repo.load_parsed_analysis(analysis_id)
        if not loaded:
            return
        analysis, meta = loaded
        self.reading_page.restore_analysis(analysis_id, analysis, meta)
        self.switch_page("reading")

    def _reanalyze(self, source_text: str) -> None:
        self.reading_page.source_edit.setPlainText(source_text)
        self.switch_page("reading")
        self.reading_page._generate_prompt()

    def _refresh_data_pages(self) -> None:
        self.history_page.refresh()
        self.knowledge_page.refresh()
        self.review_page.refresh()

    # ------------------------------------------------------------------
    def _open_settings(self) -> None:
        from paperlingo.ui.dialogs.settings_dialog import SettingsDialog

        old_theme = self.settings.theme
        old_font = self.settings.font_scale
        dlg = SettingsDialog(self.settings, self.repo, self)
        if dlg.exec():
            dlg.result_settings()
            self.settings.save(self.repo)
            if self.settings.theme != old_theme or abs(self.settings.font_scale - old_font) > 1e-6:
                self.apply_theme(self.settings.theme, self.settings.font_scale)


def _scale_font_sizes(qss: str, scale: float) -> str:
    """按比例缩放 QSS 中的主要字号。"""
    import re

    def repl(m: re.Match) -> str:
        return f"font-size: {max(9, round(int(m.group(1)) * scale))}px"

    return re.sub(r"font-size:\s*(\d+)px", repl, qss)
