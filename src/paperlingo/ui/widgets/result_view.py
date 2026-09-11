"""Analysis result view with progressive disclosure.

Top: the highest-value information (original sentence with subtle role
highlighting, natural translation, core meaning, skeleton) — the user should
understand the sentence in about ten seconds. Below: a segmented control
switching a stacked detail area (概览 / 结构 / 语法 / 词汇 / 表达 / 概念), where
each section is a compact list + detail panel instead of a wall of cards.

All AI-provided text is rendered as plain text (never interpreted as rich text).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from paperlingo.domain.analysis import PaperAnalysis
from paperlingo.ui.strings_zh_cn import (
    CONCEPT_BACKGROUND_LABEL,
    CONCEPT_IN_PAPER_LABEL,
    CORE_MEANING_LABEL,
    CORRECT_LABEL,
    DIFFICULTY_LABEL,
    EXPRESSION_USAGE_LABEL,
    EXPRESSION_WHEN_LABEL,
    EXPRESSIONS_GROUP,
    LITERAL_TRANSLATION_LABEL,
    MISUNDERSTANDINGS_LABEL,
    NATURAL_TRANSLATION_LABEL,
    PHRASE_MEANING_LABEL,
    PHRASE_USAGE_LABEL,
    PHRASES_GROUP,
    READING_STRATEGY_LABEL,
    READING_TIPS_LABEL,
    REFERENCES_LABEL,
    RESULT_TAB_CONCEPT,
    RESULT_TAB_EXPRESSION,
    RESULT_TAB_GRAMMAR,
    RESULT_TAB_OVERVIEW,
    RESULT_TAB_STRUCTURE,
    RESULT_TAB_VOCAB,
    SENTENCE_SKELETON_LABEL,
    WEB_RESEARCH_USED,
    WHY_DIFFICULT_LABEL,
    WHY_WRONG_LABEL,
    WORD_ACADEMIC_LABEL,
    WORD_COLLOCATIONS_LABEL,
    WORD_COMMON_MEANINGS_LABEL,
    WORD_IN_CONTEXT_LABEL,
    WORD_LEARN_ADD,
    WORD_LEARN_KNOWN,
    WORD_LEMMA_LABEL,
    WORD_POS_LABEL,
    WORD_WHY_LABEL,
    WRONG_LABEL,
)
from paperlingo.ui.widgets.common import _plain
from paperlingo.ui.widgets.list_detail import ListDetailPanel, detail_inset, detail_label
from paperlingo.ui.widgets.segmented import SegmentedControl
from paperlingo.ui.widgets.sentence import InteractiveSentenceWidget
from paperlingo.ui.widgets.structure_tab import SegmentExplorer


def _difficulty_badge(difficulty: int) -> QLabel:
    filled = "●" * difficulty + "○" * (5 - difficulty)
    lbl = _plain(QLabel(f"{DIFFICULTY_LABEL} {filled}"))
    lbl.setProperty("role", "tertiary")
    return lbl


def _section(title: str) -> tuple[QWidget, QVBoxLayout]:
    head = QLabel(title)
    head.setProperty("role", "h2")
    box = QWidget()
    v = QVBoxLayout(box)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(8)
    v.addWidget(head)
    return box, v


class _SectionPage(QScrollArea):
    """One scrollable page of the section stack."""

    def __init__(self) -> None:
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self._host = QWidget()
        self.v = QVBoxLayout(self._host)
        self.v.setContentsMargins(4, 12, 8, 24)
        self.v.setSpacing(12)
        self.setWidget(self._host)

    def clear(self) -> None:
        while self.v.count():
            item = self.v.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()


class ResultView(QWidget):
    """The step-3 learning view. `on_learn` is injected by the reading page."""

    TABS: ClassVar[list[tuple[str, str]]] = [
        ("overview", RESULT_TAB_OVERVIEW),
        ("structure", RESULT_TAB_STRUCTURE),
        ("grammar", RESULT_TAB_GRAMMAR),
        ("vocab", RESULT_TAB_VOCAB),
        ("expression", RESULT_TAB_EXPRESSION),
        ("concept", RESULT_TAB_CONCEPT),
    ]

    def __init__(self, palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._palette = palette
        self.on_learn: Callable[[str, str, str], None] | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # ---------------- Hero ----------------
        hero = QFrame()
        hero.setProperty("role", "card")
        hv = QVBoxLayout(hero)
        hv.setContentsMargins(20, 16, 20, 16)
        hv.setSpacing(10)

        self.sentence_widget = InteractiveSentenceWidget(palette)
        hv.addWidget(self.sentence_widget)

        self._natural = _plain(QLabel())
        self._natural.setWordWrap(True)
        self._natural.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._natural.setStyleSheet("font-size: 17px; font-weight: 600;")
        hv.addWidget(self._natural)
        self._natural_head = QLabel(NATURAL_TRANSLATION_LABEL)
        self._natural_head.setProperty("role", "tertiary")
        hv.insertWidget(hv.indexOf(self._natural), self._natural_head)

        self._core = _plain(QLabel())
        self._core.setWordWrap(True)
        self._core.setProperty("role", "secondary")
        self._core.hide()
        hv.addWidget(self._core)

        self._skeleton = _plain(QLabel())
        self._skeleton.setWordWrap(True)
        self._skeleton.setProperty("role", "tertiary")
        self._skeleton.hide()
        hv.addWidget(self._skeleton)

        self._meta_row = QHBoxLayout()
        self._meta_row.setSpacing(10)
        hv.addLayout(self._meta_row)
        root.addWidget(hero)

        # ---------------- Section navigation ----------------
        self._tabs = SegmentedControl(self.TABS)
        root.addWidget(self._tabs)

        # ---------------- Section stack ----------------
        self._stack = QStackedWidget()
        self._pages: dict[str, _SectionPage] = {}
        for key, _label in self.TABS:
            page = _SectionPage()
            self._pages[key] = page
            self._stack.addWidget(page)
        root.addWidget(self._stack, 1)

        self._tabs.selected.connect(self._on_tab)
        self._stack.setCurrentIndex(0)

    # ------------------------------------------------------------------
    def show_analysis(self, a: PaperAnalysis, word_map: dict[str, tuple[str, str]] | None = None) -> None:
        for page in self._pages.values():
            page.clear()

        self.sentence_widget.set_analysis(
            a.source_text, a.syntax.segments, a.syntax.clauses, word_map or {}
        )

        # Hero content
        t = a.translation
        self._natural.setText(t.natural or "（AI 未提供自然翻译）")
        self._natural_head.setVisible(bool(t.natural))
        self._core.setVisible(bool(t.core_meaning))
        self._core.setText(f"{CORE_MEANING_LABEL}：{t.core_meaning}" if t.core_meaning else "")
        self._skeleton.setVisible(bool(a.syntax.skeleton))
        self._skeleton.setText(f"{SENTENCE_SKELETON_LABEL}：{a.syntax.skeleton}" if a.syntax.skeleton else "")

        while self._meta_row.count():
            item = self._meta_row.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        self._meta_row.addWidget(_difficulty_badge(a.overview.difficulty))
        if a.overview.sentence_type:
            st = _plain(QLabel(a.overview.sentence_type))
            st.setProperty("role", "tertiary")
            self._meta_row.addWidget(st)
        self._meta_row.addStretch(1)

        self._build_overview(a)
        self._build_structure(a)
        self._build_grammar(a)
        self._build_vocab(a)
        self._build_expression(a)
        self._build_concept(a)
        self._tabs.select_key("overview")
        self._stack.setCurrentIndex(0)

    # ------------------------------------------------------------------
    def _on_tab(self, key: str) -> None:
        for i, (k, _label) in enumerate(self.TABS):
            if k == key:
                self._stack.setCurrentIndex(i)
                return

    # ------------------------------------------------------------------
    def _build_overview(self, a: PaperAnalysis) -> None:
        page = self._pages["overview"]
        o = a.overview

        if o.one_sentence_explanation:
            box, v = _section("这句话在干什么")
            v.addWidget(detail_label(o.one_sentence_explanation))
            page.v.addWidget(box)
        if o.difficulty_reason:
            box, v = _section(WHY_DIFFICULT_LABEL)
            v.addWidget(detail_label(o.difficulty_reason))
            page.v.addWidget(box)
        if o.reading_strategy:
            box, v = _section(READING_STRATEGY_LABEL)
            v.addWidget(detail_inset([o.reading_strategy]))
            page.v.addWidget(box)

        t = a.translation
        extra: list[str] = []
        if t.literal and t.literal != t.natural:
            extra.append(t.literal)
        extra.extend(n for n in t.translation_notes[:6] if n.strip())
        if extra:
            box, v = _section(LITERAL_TRANSLATION_LABEL)
            for line in extra:
                v.addWidget(detail_label(line, "secondary"))
            page.v.addWidget(box)

        if a.reading_tips:
            box, v = _section(READING_TIPS_LABEL)
            for tip in a.reading_tips[:5]:
                if tip.strip():
                    v.addWidget(detail_label("· " + tip, "secondary"))
            page.v.addWidget(box)

        if a.references:
            box, v = _section(REFERENCES_LABEL)
            for r in a.references[:8]:
                row = QWidget()
                rv = QVBoxLayout(row)
                rv.setContentsMargins(0, 0, 0, 0)
                rv.setSpacing(2)
                flow = QHBoxLayout()
                flow.setSpacing(8)
                expr = _plain(QLabel(r.expression))
                expr.setStyleSheet("font-weight: 600;")
                arrow = QLabel("→")
                arrow.setProperty("role", "tertiary")
                refers = _plain(QLabel(r.refers_to))
                refers.setWordWrap(True)
                flow.addWidget(expr)
                flow.addWidget(arrow)
                flow.addWidget(refers, 1)
                rv.addLayout(flow)
                if r.explanation:
                    rv.addWidget(detail_label(r.explanation, "secondary"))
                v.addWidget(row)
            page.v.addWidget(box)

        if a.misunderstandings:
            box, v = _section(MISUNDERSTANDINGS_LABEL)
            for m in a.misunderstandings[:4]:
                v.addWidget(detail_inset([
                    f"{WRONG_LABEL}：{m.wrong_interpretation}",
                    f"{WHY_WRONG_LABEL}：{m.why_wrong}" if m.why_wrong else "",
                    f"{CORRECT_LABEL}：{m.correct_interpretation}",
                ]))
            page.v.addWidget(box)

        wr = a.web_research
        if wr.used:
            src = "、".join(s.title or s.url for s in wr.sources[:3])
            note = _plain(QLabel(
                f"{WEB_RESEARCH_USED}{'：' + src if src else ''}"
                + (f"　{wr.notes}" if wr.notes else "")
            ))
            note.setWordWrap(True)
            note.setProperty("role", "tertiary")
            page.v.addWidget(note)

    # ------------------------------------------------------------------
    def _build_structure(self, a: PaperAnalysis) -> None:
        page = self._pages["structure"]
        explorer = SegmentExplorer(self._palette)
        explorer.build(a.syntax)
        page.v.addWidget(explorer)
        self._structure_explorer = explorer

    # ------------------------------------------------------------------
    def _build_grammar(self, a: PaperAnalysis) -> None:
        page = self._pages["grammar"]
        if not a.grammar_points:
            page.v.addWidget(self._empty_note("AI 未返回语法点"))
            return
        panel = ListDetailPanel()
        for g in a.grammar_points[:8]:
            sub = (g.source or "")[:60]
            panel.add_item(g.name_zh or g.name, sub, g)
        panel.selection_changed.connect(lambda row: self._show_grammar_detail(panel, row))
        page.v.addWidget(panel, 1)
        self._show_grammar_detail(panel, 0)

    def _show_grammar_detail(self, panel: ListDetailPanel, row: int) -> None:
        g = panel.item_data(row)
        if g is None:
            return
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        if g.name and g.name_zh and g.name != g.name_zh:
            en = _plain(QLabel(g.name))
            en.setProperty("role", "tertiary")
            v.addWidget(en)
        if g.explanation:
            v.addWidget(detail_label(g.explanation))
        if g.why_used_here:
            v.addWidget(detail_label(f"在这里为什么这么用：{g.why_used_here}", "secondary"))
        if g.simple_example:
            lines = [g.simple_example] + ([g.simple_example_zh] if g.simple_example_zh else [])
            v.addWidget(detail_inset(lines))
        if g.common_mistake:
            v.addWidget(detail_label(f"常见误解：{g.common_mistake}", "tertiary"))
        stars = "★" * g.importance + "☆" * (5 - g.importance)
        imp = _plain(QLabel(f"重要程度 {stars}"))
        imp.setProperty("role", "tertiary")
        v.addWidget(imp)
        v.addStretch(1)
        panel.set_detail_widget(w)

    # ------------------------------------------------------------------
    def _build_vocab(self, a: PaperAnalysis) -> None:
        page = self._pages["vocab"]
        if not a.words:
            page.v.addWidget(self._empty_note("AI 未返回值得学习的单词"))
            return
        panel = ListDetailPanel()
        for wd in a.words[:12]:
            sub = " · ".join(x for x in (wd.pos_zh or wd.pos, (wd.meaning_in_context or "")[:40]) if x)
            panel.add_item(wd.surface or wd.lemma, sub, wd)
        panel.selection_changed.connect(lambda row: self._show_word_detail(panel, row))
        page.v.addWidget(panel, 1)
        self._show_word_detail(panel, 0)

    def _show_word_detail(self, panel: ListDetailPanel, row: int) -> None:
        wd = panel.item_data(row)
        if wd is None:
            return
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        # Priority hierarchy per product spec: surface, meaning in context,
        # lemma+POS, why here, academic meaning, collocations, general
        # meanings, learning state.
        ctx = detail_inset([wd.meaning_in_context or "—"]) if wd.meaning_in_context else None
        head = QLabel(WORD_IN_CONTEXT_LABEL)
        head.setProperty("role", "tertiary")
        if ctx is not None:
            v.addWidget(head)
            v.addWidget(ctx)
        meta_bits = []
        if wd.lemma and wd.lemma != wd.surface:
            meta_bits.append(f"{WORD_LEMMA_LABEL}：{wd.lemma}")
        if wd.pos or wd.pos_zh:
            meta_bits.append(f"{WORD_POS_LABEL}：{wd.pos_zh or wd.pos}")
        if wd.phonetic:
            meta_bits.append(wd.phonetic)
        if meta_bits:
            v.addWidget(detail_label("　".join(meta_bits), "secondary"))
        if wd.why_here:
            v.addWidget(detail_label(f"{WORD_WHY_LABEL}：{wd.why_here}", "secondary"))
        if wd.academic_meaning:
            v.addWidget(detail_label(f"{WORD_ACADEMIC_LABEL}：{wd.academic_meaning}", "secondary"))
        if wd.collocations:
            v.addWidget(detail_label(f"{WORD_COLLOCATIONS_LABEL}：" + "　".join(wd.collocations[:5]), "secondary"))
        if wd.common_meanings:
            v.addWidget(detail_label(f"{WORD_COMMON_MEANINGS_LABEL}：" + "、".join(wd.common_meanings[:5]), "tertiary"))

        if self.on_learn is not None:
            btns = QHBoxLayout()
            btns.addStretch(1)
            key = (wd.lemma or wd.surface).strip().lower()
            known = QPushButton(WORD_LEARN_KNOWN)
            known.setProperty("role", "ghost")
            known.clicked.connect(lambda: self.on_learn("word", key, "known"))  # type: ignore[misc]
            learn = QPushButton(WORD_LEARN_ADD)
            learn.setProperty("role", "chip")
            learn.clicked.connect(lambda: self.on_learn("word", key, "unfamiliar"))  # type: ignore[misc]
            btns.addWidget(known)
            btns.addWidget(learn)
            v.addLayout(btns)
        v.addStretch(1)
        panel.set_detail_widget(w)

    # ------------------------------------------------------------------
    def _build_expression(self, a: PaperAnalysis) -> None:
        page = self._pages["expression"]
        if not a.phrases and not a.academic_expressions:
            page.v.addWidget(self._empty_note("AI 未返回短语或学术表达"))
            return
        panel = ListDetailPanel()
        for p in a.phrases[:8]:
            panel.add_item(p.text, PHRASES_GROUP, ("phrase", p))
        for e in a.academic_expressions[:6]:
            panel.add_item(e.text, EXPRESSIONS_GROUP, ("expression", e))
        panel.selection_changed.connect(lambda row: self._show_expression_detail(panel, row))
        page.v.addWidget(panel, 1)
        self._show_expression_detail(panel, 0)

    def _show_expression_detail(self, panel: ListDetailPanel, row: int) -> None:
        data = panel.item_data(row)
        if data is None:
            return
        kind, obj = data
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        tag = QLabel(PHRASES_GROUP if kind == "phrase" else EXPRESSIONS_GROUP)
        tag.setProperty("role", "tertiary")
        v.addWidget(tag)
        if kind == "phrase":
            p = obj
            if p.meaning:
                v.addWidget(detail_label(f"{PHRASE_MEANING_LABEL}：{p.meaning}"))
            if p.explanation:
                v.addWidget(detail_label(p.explanation, "secondary"))
            if p.academic_usage:
                v.addWidget(detail_label(f"{PHRASE_USAGE_LABEL}：{p.academic_usage}", "secondary"))
            if p.example:
                lines = [p.example] + ([p.example_zh] if p.example_zh else [])
                v.addWidget(detail_inset(lines))
            if self.on_learn is not None:
                btns = QHBoxLayout()
                btns.addStretch(1)
                known = QPushButton(WORD_LEARN_KNOWN)
                known.setProperty("role", "ghost")
                known.clicked.connect(lambda: self.on_learn("phrase", p.text, "known"))  # type: ignore[misc]
                learn = QPushButton(WORD_LEARN_ADD)
                learn.setProperty("role", "chip")
                learn.clicked.connect(lambda: self.on_learn("phrase", p.text, "unfamiliar"))  # type: ignore[misc]
                btns.addWidget(known)
                btns.addWidget(learn)
                v.addLayout(btns)
        else:
            e = obj
            if e.meaning:
                v.addWidget(detail_label(f"{PHRASE_MEANING_LABEL}：{e.meaning}"))
            if e.usage:
                v.addWidget(detail_label(f"{EXPRESSION_USAGE_LABEL}：{e.usage}", "secondary"))
            if e.when_to_use:
                v.addWidget(detail_label(f"{EXPRESSION_WHEN_LABEL}：{e.when_to_use}", "secondary"))
            if e.example:
                lines = [e.example] + ([e.example_zh] if e.example_zh else [])
                v.addWidget(detail_inset(lines))
        v.addStretch(1)
        panel.set_detail_widget(w)

    # ------------------------------------------------------------------
    def _build_concept(self, a: PaperAnalysis) -> None:
        page = self._pages["concept"]
        if not a.concepts:
            page.v.addWidget(self._empty_note("AI 未返回专业概念"))
            return
        panel = ListDetailPanel()
        for c in a.concepts[:6]:
            panel.add_item(c.term, c.translation, c)
        panel.selection_changed.connect(lambda row: self._show_concept_detail(panel, row))
        page.v.addWidget(panel, 1)
        self._show_concept_detail(panel, 0)

    def _show_concept_detail(self, panel: ListDetailPanel, row: int) -> None:
        c = panel.item_data(row)
        if c is None:
            return
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        if c.simple_explanation:
            v.addWidget(detail_label(c.simple_explanation))
        if c.meaning_in_this_paper:
            v.addWidget(detail_label(f"{CONCEPT_IN_PAPER_LABEL}：{c.meaning_in_this_paper}", "secondary"))
        if c.background_needed:
            tag = _plain(QLabel(CONCEPT_BACKGROUND_LABEL))
            tag.setProperty("role", "tertiary")
            v.addWidget(tag)
        v.addStretch(1)
        panel.set_detail_widget(w)

    def _empty_note(self, text: str) -> QLabel:
        lbl = _plain(QLabel(text))
        lbl.setProperty("role", "tertiary")
        return lbl
