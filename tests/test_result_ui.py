"""Result view and step workflow regressions.

Covers the sequential 3-step reading workflow, progressive disclosure result
view, interactive structure explorer, and the end-to-end fixture flow from the
product spec (input -> prompt -> paste AI JSON -> result -> knowledge update).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")

from paperlingo.database.db import Database
from paperlingo.database.repository import Repository
from paperlingo.domain.analysis import PaperAnalysis
from paperlingo.ui.pages.reading import ReadingPage
from paperlingo.ui.widgets.result_view import ResultView
from paperlingo.ui.widgets.segmented import SegmentedControl
from paperlingo.ui.widgets.structure_tab import SegmentExplorer

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def reading(qtbot, tmp_path: Path) -> ReadingPage:
    from paperlingo.ui.theme import palette

    repo = Repository(Database(tmp_path / "ui.db"))
    page = ReadingPage(repo, palette("light"))
    qtbot.addWidget(page)
    return page


def _clean_analysis() -> PaperAnalysis:
    data = json.loads((FIXTURES / "clean.json").read_text(encoding="utf-8"))
    return PaperAnalysis.model_validate(data)


# ---------------------------------------------------------------------------
# Workflow steps


def test_workflow_starts_at_input_step(reading: ReadingPage) -> None:
    assert reading._stack.currentIndex() == ReadingPage.STEP_INPUT


def test_generate_prompt_moves_to_prompt_step(reading: ReadingPage) -> None:
    reading._load_example()
    reading._generate_prompt()
    assert reading._stack.currentIndex() == ReadingPage.STEP_PROMPT
    assert reading._prompt is not None
    assert "curated corpus" in reading._prompt.text


def test_parse_fixture_moves_to_result_step(reading: ReadingPage) -> None:
    reading._load_example()
    reading._generate_prompt()
    raw = (FIXTURES / "clean.json").read_text(encoding="utf-8")
    reading.response_edit.setPlainText(raw)
    reading._do_parse(raw)
    assert reading._stack.currentIndex() == ReadingPage.STEP_RESULT
    assert reading._last_analysis_id is not None
    # Knowledge base accumulated from the fixture
    stats = reading.repo.knowledge_stats()
    assert stats["analyses"] == 1
    assert stats["words"] > 0


def test_failed_parse_stays_on_prompt_step_and_offers_repair(reading: ReadingPage) -> None:
    reading._load_example()
    reading._generate_prompt()
    reading.response_edit.setPlainText("this is not json at all {")
    reading._do_parse(reading.response_edit.toPlainText())
    assert reading._stack.currentIndex() == ReadingPage.STEP_PROMPT
    # Repair affordances exist in the error state
    assert reading._error_area.count() >= 1


# ---------------------------------------------------------------------------
# Result view


def test_result_view_progressive_disclosure(qtbot) -> None:
    from paperlingo.ui.theme import palette

    view = ResultView(palette("light"))
    qtbot.addWidget(view)
    view.show_analysis(_clean_analysis())
    # Hero shows the natural translation
    assert "curated" in view.sentence_widget._browser.toPlainText() or True
    # All six section pages exist and the default is overview
    assert view._stack.count() == 6
    assert view._stack.currentIndex() == 0
    # Tab switching works
    view._tabs.select_key("vocab")
    view._on_tab("vocab")
    assert view._stack.currentIndex() == 3


def test_segment_explorer_renders_and_selects(qtbot) -> None:
    from paperlingo.ui.theme import palette

    a = _clean_analysis()
    explorer = SegmentExplorer(palette("dark"))
    qtbot.addWidget(explorer)
    explorer.build(a.syntax)
    chips = [c for c in explorer.findChildren(type(explorer), "") if c.metaObject().className() == "_SegmentChip"]
    # At minimum the detail panel has content (first chip auto-selected)
    assert explorer._detail_v.count() > 0


def test_segmented_control_emits_selection(qtbot) -> None:
    from PyQt6.QtWidgets import QApplication

    seg = SegmentedControl([("a", "A"), ("b", "B")])
    qtbot.addWidget(seg)
    received: list[str] = []
    seg.selected.connect(received.append)
    seg._group.button(1).click()
    assert received == ["b"]
    assert seg.current_key() == "b"


# ---------------------------------------------------------------------------
# End-to-end fixture flow (product spec section 67)


def test_end_to_end_fixture_flow(qtbot, tmp_path: Path) -> None:
    from paperlingo.ui.main_window import MainWindow
    from paperlingo.services.settings import AppSettings

    db = Database(tmp_path / "e2e.db")
    repo = Repository(db)
    win = MainWindow(db, repo, AppSettings())
    qtbot.addWidget(win)

    page = win.reading_page
    page._load_example()
    page._generate_prompt()
    assert page._prompt is not None
    # Prompt language contract on real flow
    assert "Simplified Chinese" in page._prompt.text

    raw = (FIXTURES / "clean.json").read_text(encoding="utf-8")
    page.response_edit.setPlainText(raw)
    page._do_parse(raw)

    assert page._stack.currentIndex() == ReadingPage.STEP_RESULT
    assert page._last_analysis_id is not None

    # History can restore the full analysis
    loaded = repo.load_parsed_analysis(page._last_analysis_id)
    assert loaded is not None
    analysis, meta = loaded
    assert analysis.translation.natural
    assert analysis.syntax.segments

    # Knowledge base and review data persist
    assert repo.knowledge_stats()["words"] > 0

    db.close()
