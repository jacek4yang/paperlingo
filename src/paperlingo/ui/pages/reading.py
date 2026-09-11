"""Reading page: the sequential 3-step workflow.

Step 1  输入英文        one large editor; paper metadata stays collapsed
Step 2  提示词 / AI 结果 success card (copy / view prompt) + paste + parse
Step 3  理解与学习      progressive-disclosure result view

Implemented with an internal QStackedWidget and subtle state indication —
no decorative stepper.
"""

from __future__ import annotations

import logging
from contextlib import suppress

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from paperlingo.database.repository import Repository
from paperlingo.domain.analysis import DEPTH_LABELS, AnalysisRequest, PaperAnalysis
from paperlingo.domain.paper import DOMAIN_OPTIONS
from paperlingo.parser.response_parser import parse_response
from paperlingo.prompt.compiler import CompiledPrompt, PromptCompiler, compile_repair_prompt
from paperlingo.prompt.profiles import list_profiles
from paperlingo.services.clipboard import ClipboardError, read_text, write_text
from paperlingo.services.draft import DraftStore
from paperlingo.ui import strings_zh_cn as s
from paperlingo.ui.theme import Palette
from paperlingo.ui.widgets.common import CollapsibleCard, CopyButton, EmptyState, ErrorState
from paperlingo.ui.widgets.result_view import ResultView

logger = logging.getLogger(__name__)

DEPTHS = list(DEPTH_LABELS.keys())

_STEP_HINTS = ("Step 1 · 输入英文", "Step 2 · 提示词与 AI 结果", "Step 3 · 理解与学习")


def _step_hint(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("role", "tertiary")
    return lbl


class ReadingPage(QWidget):
    #: emitted with the analysis id after a successful parse + save
    analysis_saved = pyqtSignal(int)

    STEP_INPUT = 0
    STEP_PROMPT = 1
    STEP_RESULT = 2

    def __init__(self, repo: Repository, palette: Palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.repo = repo
        self._palette = palette
        self._prompt: CompiledPrompt | None = None
        self._compiler = PromptCompiler()
        self._draft = DraftStore(repo)
        self._last_analysis_id: int | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        self._build_input_step()
        self._build_prompt_step()
        self._build_result_step()
        self._stack.setCurrentIndex(self.STEP_INPUT)

        self._apply_defaults()
        self._load_draft()

        # Shortcuts: Ctrl+Enter is the primary action of the current step;
        # standard editing shortcuts are never hijacked.
        QShortcut(QKeySequence("Ctrl+Return"), self, self._primary_action)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, self._copy_prompt_action)

        # Draft autosave
        self._draft_timer = QTimer(self)
        self._draft_timer.setInterval(3000)
        self._draft_timer.timeout.connect(self._save_draft)
        self._draft_timer.start()
        for edit in (
            self.source_edit, self._prev_edit, self._next_edit,
            self.response_edit,
        ):
            edit.textChanged.connect(self._save_draft)

    # ==================================================================
    # Step 1 — English input
    # ==================================================================
    def _build_input_step(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(48, 32, 48, 32)
        v.setSpacing(10)
        v.setAlignment(Qt.AlignmentFlag.AlignTop)

        v.addWidget(_step_hint(_STEP_HINTS[0]))

        title = QLabel(s.STEP1_TITLE)
        title.setProperty("role", "title")
        f = title.font()
        f.setPointSizeF(f.pointSizeF() + 8)
        title.setFont(f)
        v.addWidget(title)

        subtitle = QLabel(s.STEP1_SUBTITLE)
        subtitle.setProperty("role", "secondary")
        v.addWidget(subtitle)
        v.addSpacing(10)

        self.source_edit = QPlainTextEdit()
        self.source_edit.setPlaceholderText(s.SOURCE_PLACEHOLDER)
        self.source_edit.setMinimumHeight(180)
        self.source_edit.setStyleSheet("font-size: 16px;")
        v.addWidget(self.source_edit)

        counter_row = QHBoxLayout()
        self._counter = QLabel(f"0 {s.WORDS_SUFFIX} · 0 {s.CHARS_SUFFIX}")
        self._counter.setProperty("role", "tertiary")
        counter_row.addStretch(1)
        counter_row.addWidget(self._counter)
        v.addLayout(counter_row)
        self.source_edit.textChanged.connect(self._update_counter)

        # Paper metadata: collapsed, low emphasis
        self._info_card = CollapsibleCard(s.PAPER_INFO_SECTION, expanded=False)
        hint = QLabel(s.PAPER_INFO_HINT)
        hint.setProperty("role", "tertiary")
        hint.setWordWrap(True)
        self._info_card.add_content(hint)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        def _field(placeholder: str) -> QLineEdit:
            e = QLineEdit()
            e.setPlaceholderText(placeholder)
            return e

        self.title_edit = _field(s.PAPER_TITLE_LABEL)
        self.doi_edit = _field(s.DOI_LABEL)
        self.authors_edit = _field(s.AUTHORS_LABEL)
        self.domain_combo = QComboBox()
        for value, label in DOMAIN_OPTIONS:
            # Stable English value feeds the prompt; the label is UI-only.
            self.domain_combo.addItem(label, value)
        grid.addWidget(self.title_edit, 0, 0)
        grid.addWidget(self.doi_edit, 0, 1)
        grid.addWidget(self.authors_edit, 1, 0)
        self.domain_combo.setCurrentIndex(0)
        grid.addWidget(self.domain_combo, 1, 1)
        self._info_card.add_content_layout(grid)

        self._prev_edit = QPlainTextEdit()
        self._prev_edit.setPlaceholderText(s.PREV_CONTEXT_LABEL)
        self._prev_edit.setFixedHeight(56)
        self._next_edit = QPlainTextEdit()
        self._next_edit.setPlaceholderText(s.NEXT_CONTEXT_LABEL)
        self._next_edit.setFixedHeight(56)
        self._info_card.add_content(self._prev_edit)
        self._info_card.add_content(self._next_edit)

        opts_row = QHBoxLayout()
        self.depth_combo = QComboBox()
        for d in DEPTHS:
            self.depth_combo.addItem(DEPTH_LABELS[d], d)
        self.profile_combo = QComboBox()
        for prof in list_profiles():
            self.profile_combo.addItem(prof.display_name, prof.profile_id)
        depth_lbl = QLabel(s.DEPTH_LABEL)
        depth_lbl.setProperty("role", "secondary")
        profile_lbl = QLabel(s.PROFILE_LABEL)
        profile_lbl.setProperty("role", "secondary")
        opts_row.addWidget(depth_lbl)
        opts_row.addWidget(self.depth_combo, 1)
        opts_row.addSpacing(12)
        opts_row.addWidget(profile_lbl)
        opts_row.addWidget(self.profile_combo, 1)
        self._info_card.add_content_layout(opts_row)

        v.addWidget(self._info_card)
        v.addSpacing(12)

        actions = QHBoxLayout()
        self._gen_btn = QPushButton(s.GENERATE_PROMPT)
        self._gen_btn.setProperty("role", "primary")
        self._gen_btn.clicked.connect(self._generate_prompt)
        self._example_btn = QPushButton(s.LOAD_EXAMPLE)
        self._example_btn.setProperty("role", "ghost")
        self._example_btn.clicked.connect(self._load_example)
        actions.addWidget(self._example_btn)
        actions.addStretch(1)
        actions.addWidget(self._gen_btn)
        v.addLayout(actions)

        self._input_error_area = QVBoxLayout()
        v.addLayout(self._input_error_area)

        scroll.setWidget(page)
        self._stack.addWidget(scroll)

    # ==================================================================
    # Step 2 — prompt + AI response
    # ==================================================================
    def _build_prompt_step(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(48, 32, 48, 32)
        v.setSpacing(10)
        v.setAlignment(Qt.AlignmentFlag.AlignTop)

        v.addWidget(_step_hint(_STEP_HINTS[1]))

        # Success card
        card = QWidget()
        card.setProperty("role", "card")
        cv = QVBoxLayout(card)
        cv.setContentsMargins(20, 16, 20, 16)
        cv.setSpacing(8)
        t = QLabel(s.STEP2_TITLE)
        t.setProperty("role", "title")
        cv.addWidget(t)
        sub = QLabel(s.STEP2_SUBTITLE)
        sub.setProperty("role", "secondary")
        sub.setWordWrap(True)
        cv.addWidget(sub)
        row = QHBoxLayout()
        self._copy_btn = CopyButton(lambda: self._prompt.text if self._prompt else "", label=s.COPY_PROMPT)
        self._copy_btn.setProperty("role", "primary")
        self._view_btn = QPushButton(s.VIEW_PROMPT)
        self._view_btn.clicked.connect(self._show_prompt_dialog)
        row.addWidget(self._copy_btn)
        row.addWidget(self._view_btn)
        row.addStretch(1)
        cv.addLayout(row)
        v.addWidget(card)

        # Paste AI response
        head = QLabel(s.PASTE_RESPONSE_SECTION)
        head.setProperty("role", "h2")
        v.addWidget(head)
        self.response_edit = QPlainTextEdit()
        self.response_edit.setPlaceholderText(s.RESPONSE_PLACEHOLDER)
        self.response_edit.setMinimumHeight(150)
        v.addWidget(self.response_edit)

        actions = QHBoxLayout()
        self._from_clip_btn = QPushButton(s.PASTE_FROM_CLIPBOARD)
        self._from_clip_btn.clicked.connect(self._paste_from_clipboard)
        self._parse_btn = QPushButton(s.PARSE_RESULT)
        self._parse_btn.setProperty("role", "primary")
        self._parse_btn.clicked.connect(self._parse_response)
        self._back_btn = QPushButton(s.BACK_TO_EDIT)
        self._back_btn.setProperty("role", "ghost")
        self._back_btn.clicked.connect(lambda: self._goto_step(self.STEP_INPUT))
        actions.addWidget(self._back_btn)
        actions.addStretch(1)
        actions.addWidget(self._from_clip_btn)
        actions.addWidget(self._parse_btn)
        v.addLayout(actions)

        self._error_area = QVBoxLayout()
        v.addLayout(self._error_area)

        scroll.setWidget(page)
        self._stack.addWidget(scroll)

    # ==================================================================
    # Step 3 — result
    # ==================================================================
    def _build_result_step(self) -> None:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(32, 24, 32, 16)
        v.setSpacing(10)

        top = QHBoxLayout()
        top.addWidget(_step_hint(_STEP_HINTS[2]))
        top.addStretch(1)
        self._ingest_warning = QLabel("部分知识点未能沉淀到知识库，详情见日志")
        self._ingest_warning.setProperty("role", "tertiary")
        self._ingest_warning.hide()
        top.addWidget(self._ingest_warning)
        back = QPushButton(s.BACK_TO_EDIT)
        back.setProperty("role", "ghost")
        back.clicked.connect(lambda: self._goto_step(self.STEP_INPUT))
        top.addWidget(back)
        v.addLayout(top)

        self.result_view = ResultView(self._palette)
        self.result_view.on_learn = self._add_learning_item
        v.addWidget(self.result_view, 1)

        self._stack.addWidget(page)

    # ==================================================================
    def _apply_defaults(self) -> None:
        from paperlingo.services.settings import AppSettings

        settings = AppSettings.load(self.repo)
        idx = self.depth_combo.findData(settings.default_depth)
        if idx >= 0:
            self.depth_combo.setCurrentIndex(idx)
        idx = self.profile_combo.findData(settings.default_profile)
        if idx >= 0:
            self.profile_combo.setCurrentIndex(idx)

    def _goto_step(self, step: int) -> None:
        self._stack.setCurrentIndex(step)

    def _primary_action(self) -> None:
        step = self._stack.currentIndex()
        if step == self.STEP_INPUT:
            self._generate_prompt()
        elif step == self.STEP_PROMPT:
            self._parse_response()

    # ------------------------------------------------------------------
    def _update_counter(self) -> None:
        text = self.source_edit.toPlainText()
        words = len([w for w in text.split() if w.strip()])
        self._counter.setText(f"{words} {s.WORDS_SUFFIX} · {len(text)} {s.CHARS_SUFFIX}")

    def _collect_request(self) -> AnalysisRequest:
        from paperlingo.domain.paper import PaperInfo

        info = PaperInfo(
            title=self.title_edit.text(),
            doi_or_url=self.doi_edit.text(),
            authors=self.authors_edit.text(),
            domain=self.domain_combo.currentData() or "auto",
        )
        depth = self.depth_combo.currentData() or "standard"
        return AnalysisRequest(
            source_text=self.source_edit.toPlainText(),
            previous_context=self._prev_edit.toPlainText(),
            following_context=self._next_edit.toPlainText(),
            paper_title=info.title,
            doi_or_url=info.doi_or_url,
            authors=info.authors,
            domain=info.domain,
            analysis_depth=depth,
            known_knowledge_profile=self._knowledge_profile_text(),
        )

    def _knowledge_profile_text(self) -> str:
        """Build the learner-profile snippet injected into the prompt.

        Always generated in English (prompt language contract), e.g.
        "Weak learning categories: vocabulary=4, grammar=2."
        """
        try:
            stats = self.repo.knowledge_stats()
        except Exception:
            return ""
        if stats["analyses"] < 3:
            return ""
        rows = self.repo.weak_learning_counts()
        name_map = {"word": "vocabulary", "phrase": "phrases", "grammar": "grammar",
                    "expression": "expressions", "concept": "concepts"}
        weak: list[str] = []
        for r in rows:
            en = name_map.get(r["item_type"])
            if en and r["c"] >= 2:
                weak.append(f"{en}={r['c']}")
        if not weak:
            return ""
        return "Weak learning categories: " + ", ".join(weak[:4]) + "."

    # ------------------------------------------------------------------
    def _generate_prompt(self) -> None:
        self._clear_errors()
        try:
            req = self._collect_request()
            self._prompt = self._compiler.compile(
                req, self.profile_combo.currentData() or "generic"
            )
        except Exception as e:
            self._show_input_error(s.GENERATE_ERROR_TITLE, str(e))
            return
        # A fresh prompt lands on step 2; copy it right away to save a step.
        self._copy_btn._copy()
        self._goto_step(self.STEP_PROMPT)
        self.response_edit.setFocus()

    def _copy_prompt_action(self) -> None:
        if self._prompt:
            self._copy_btn._copy()

    def _show_prompt_dialog(self) -> None:
        from paperlingo.ui.dialogs.prompt_dialog import PromptDialog

        if self._prompt:
            PromptDialog(self._prompt, self, title=s.PROMPT_DIALOG_TITLE).exec()

    # ------------------------------------------------------------------
    def _paste_from_clipboard(self) -> None:
        # Clipboard contention is a common, non-fatal case: ignore quietly.
        with suppress(ClipboardError):
            self.response_edit.setPlainText(read_text())

    def _parse_response(self) -> None:
        raw = self.response_edit.toPlainText()
        self._clear_errors()
        # Defer one frame so the UI stays responsive; parsing is fast but the
        # Pydantic validation can be heavier for large payloads.
        QTimer.singleShot(30, lambda: self._do_parse(raw))

    def _do_parse(self, raw: str) -> None:
        result = parse_response(raw)
        if not result.ok or result.data is None:
            err = result.error
            self._show_parse_error(s.PARSE_ERROR_TITLE, err.describe() if err else "unknown error", raw)
            return
        try:
            analysis = PaperAnalysis.model_validate(result.data)
        except Exception as e:
            self._show_parse_error(s.VALIDATION_ERROR_TITLE, str(e)[:400], raw)
            return

        req = self._collect_request()
        analysis_id = self.repo.save_analysis(
            source_text=analysis.source_text or req.source_text,
            previous_context=req.previous_context,
            following_context=req.following_context,
            analysis_depth=req.analysis_depth,
            profile_id=self._prompt.profile_id if self._prompt else "generic",
            paper_title=req.paper_title,
            paper_doi_or_url=req.doi_or_url,
            paper_authors=req.authors,
            paper_domain=req.domain,
            prompt_text=self._prompt.text if self._prompt else "",
            prompt_version=self._prompt.template_version if self._prompt else "",
            raw_response=raw,
            parsed=result.data,
        )
        self._show_analysis(analysis)
        self._last_analysis_id = analysis_id
        self._ingest_warning.setVisible(bool(self.repo.last_ingest_error))
        self._draft.clear()
        self._goto_step(self.STEP_RESULT)
        self.analysis_saved.emit(analysis_id)

    # ------------------------------------------------------------------
    def _show_analysis(self, analysis: PaperAnalysis) -> None:
        # Map word surfaces to role colors for the interactive sentence.
        word_map: dict[str, tuple[str, str]] = {}
        for w in analysis.words:
            if not w.surface:
                continue
            info = f"{w.pos_zh or ''}\n{s.WORD_IN_CONTEXT_LABEL}：{w.meaning_in_context}"
            if w.lemma and w.lemma != w.surface:
                info += f"\n{s.WORD_LEMMA_LABEL}：{w.lemma}"
            word_map[w.surface] = ("role_misc", info)
        self.result_view.show_analysis(analysis, word_map)

    def _show_input_error(self, title: str, detail: str) -> None:
        self._clear_errors()
        self._input_error_area.addWidget(ErrorState(title, detail))

    def _show_parse_error(self, title: str, detail: str, raw: str) -> None:
        self._clear_errors()
        buttons: list[tuple[str, object]] = []
        if raw:
            def copy_repair() -> None:
                write_text(compile_repair_prompt("JSON parse failed", raw))

            def view_raw() -> None:
                from paperlingo.prompt.compiler import CompiledPrompt
                from paperlingo.ui.dialogs.prompt_dialog import PromptDialog

                cp = CompiledPrompt(text=raw, template_id="raw", template_version="raw", profile_id="")
                PromptDialog(cp, self, title=s.RAW_RESPONSE_DIALOG_TITLE).exec()

            buttons.append((s.COPY_REPAIR_PROMPT, copy_repair))
            buttons.append((s.VIEW_RAW_RESPONSE, view_raw))
        self._error_area.addWidget(ErrorState(title, detail, buttons))  # type: ignore[arg-type]

    def _clear_errors(self) -> None:
        for area in (self._error_area, self._input_error_area):
            while area.count():
                item = area.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

    # ------------------------------------------------------------------
    def _add_learning_item(self, item_type: str, key: str, state: str) -> None:
        from paperlingo.domain.learning import MasteryStatus

        ref_id = self.repo.find_knowledge_item_id(item_type, key)
        if ref_id is not None:
            self.repo.set_mastery(item_type, ref_id, MasteryStatus(state))

    def _load_example(self) -> None:
        self.source_edit.setPlainText(
            "In this survey, we address this gap through a curated corpus of 247 papers "
            "and a lifecycle-based, systems-oriented analytical framework."
        )
        self.source_edit.setFocus()

    # ------------------------------------------------------------------
    def _save_draft(self) -> None:
        self._draft.save(
            {
                "source_text": self.source_edit.toPlainText(),
                "previous_context": self._prev_edit.toPlainText(),
                "following_context": self._next_edit.toPlainText(),
                "paper_title": self.title_edit.text(),
                "doi_or_url": self.doi_edit.text(),
                "authors": self.authors_edit.text(),
                "domain": self.domain_combo.currentData(),
                "analysis_depth": self.depth_combo.currentData(),
                "profile_id": self.profile_combo.currentData(),
                "response_text": self.response_edit.toPlainText()[:100000],
            }
        )

    def _load_draft(self) -> None:
        data = self._draft.load()
        if not data:
            return
        if data.get("source_text"):
            self.source_edit.setPlainText(data["source_text"])
        self._prev_edit.setPlainText(data.get("previous_context", ""))
        self._next_edit.setPlainText(data.get("following_context", ""))
        self.title_edit.setText(data.get("paper_title", ""))
        self.doi_edit.setText(data.get("doi_or_url", ""))
        self.authors_edit.setText(data.get("authors", ""))
        for combo, key in ((self.depth_combo, "analysis_depth"), (self.profile_combo, "profile_id"),
                           (self.domain_combo, "domain")):
            idx = combo.findData(data.get(key))
            if idx >= 0:
                combo.setCurrentIndex(idx)
        if data.get("response_text"):
            self.response_edit.setPlainText(data["response_text"])

    # ------------------------------------------------------------------
    def restore_analysis(self, analysis_id: int, analysis: PaperAnalysis, meta: dict) -> None:
        """History restore: fill the inputs and show the stored result."""
        self.source_edit.setPlainText(analysis.source_text)
        self._prev_edit.setPlainText(meta.get("previous_context", ""))
        self._next_edit.setPlainText(meta.get("following_context", ""))
        self.title_edit.setText(meta.get("paper_title", ""))
        self.doi_edit.setText(meta.get("paper_doi", ""))
        self.authors_edit.setText(meta.get("paper_authors", ""))
        self._show_analysis(analysis)
        self._last_analysis_id = analysis_id
        self._ingest_warning.hide()
        self._goto_step(self.STEP_RESULT)

    # ------------------------------------------------------------------
    @property
    def prompt_text(self) -> str:
        return self._prompt.text if self._prompt else ""


# EmptyState re-exported for compatibility with older imports
__all__ = ["EmptyState", "ReadingPage"]
