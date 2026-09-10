"""UI smoke test：能启动主窗口、切页、加载示例。"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")

from paperlingo.database.db import Database
from paperlingo.database.repository import Repository
from paperlingo.services.settings import AppSettings
from paperlingo.ui.main_window import MainWindow
from paperlingo.ui.theme import build_qss, palette


@pytest.fixture
def window(qtbot, tmp_path: Path) -> MainWindow:
    db = Database(tmp_path / "ui.db")
    repo = Repository(db)
    settings = AppSettings()
    win = MainWindow(db, repo, settings)
    qtbot.addWidget(win)
    win.show()
    return win


def test_window_starts(window: MainWindow) -> None:
    assert window.windowTitle() == "PaperLingo"
    assert window.reading_page.isVisible() or window.stack.currentWidget() is window.reading_page


def test_switch_pages(window: MainWindow) -> None:
    window.switch_page("history")
    assert window.stack.currentWidget() is window.history_page
    window.switch_page("knowledge")
    assert window.stack.currentWidget() is window.knowledge_page
    window.switch_page("review")
    assert window.stack.currentWidget() is window.review_page
    window.switch_page("reading")
    assert window.stack.currentWidget() is window.reading_page


def test_load_example_and_generate_prompt(window: MainWindow) -> None:
    window.reading_page._load_example()
    text = window.reading_page.source_edit.toPlainText()
    assert "curated corpus" in text
    window.reading_page._generate_prompt()
    assert window.reading_page._prompt is not None
    assert "curated corpus" in window.reading_page._prompt.text


def test_qss_builds_for_both_themes() -> None:
    light = build_qss(palette("light"))
    dark = build_qss(palette("dark"))
    assert "QPushButton" in light
    assert "QPushButton" in dark
    assert light != dark


def test_ai_text_rendered_as_plain_text(qtbot) -> None:
    """AI 内容含 HTML 标签时必须按纯文本渲染，不得被解释为富文本。"""
    from PyQt6.QtCore import Qt

    from paperlingo.ui.widgets.common import _flow_text_label

    malicious = '<img src="http://x/y.png"><b>bold</b><script>alert(1)</script>'
    lbl = _flow_text_label(malicious)
    qtbot.addWidget(lbl)
    assert lbl.textFormat() == Qt.TextFormat.PlainText
    assert lbl.text() == malicious  # 文本原样保留，未被解释
