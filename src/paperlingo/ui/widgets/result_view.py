"""分析结果视图：渐进式展示（先翻译/核心含义/主干，再折叠的深入内容）。"""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from paperlingo.domain.analysis import PaperAnalysis
from paperlingo.ui.theme import Palette
from paperlingo.ui.widgets.common import (
    AcademicExpressionCard,
    Card,
    CollapsibleCard,
    ConceptCard,
    GrammarCard,
    MisunderstandingCard,
    PhraseCard,
    ReferenceCard,
    TranslationCard,
    WordCard,
    _plain,
)
from paperlingo.ui.widgets.sentence import InteractiveSentenceWidget
from paperlingo.ui.widgets.structure import StructureView

SECTION_WORDS = "words"
SECTION_SYNTAX = "syntax"
SECTION_GRAMMAR = "grammar"
SECTION_REFERENCES = "references"
SECTION_CONCEPTS = "concepts"
SECTION_MISUNDERSTANDINGS = "misunderstandings"


class ResultView(QScrollArea):
    """滚动结果区。signal 通过回调把定位请求发给父级。"""

    def __init__(self, palette: Palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._palette = palette
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self._sections: dict[str, QWidget] = {}

        self._container = QWidget()
        self._v = QVBoxLayout(self._container)
        self._v.setContentsMargins(4, 4, 8, 24)
        self._v.setSpacing(14)
        self.setWidget(self._container)

        # 顶部：原句（可交互）
        self.sentence_widget = InteractiveSentenceWidget(palette)
        self._v.addWidget(self.sentence_widget)

        self.on_learn: object | None = None  # 由 ReadingPage 注入

    # ------------------------------------------------------------------
    def show_analysis(self, a: PaperAnalysis, word_color_map: dict[str, tuple[str, str]] | None = None) -> None:
        self.clear()
        p = self._palette

        # 顶部核心区：翻译卡 + 总览卡
        t = a.translation
        if t.natural or t.literal or t.core_meaning or t.translation_notes:
            self._v.addWidget(TranslationCard(t.natural, t.literal, t.core_meaning, t.translation_notes))
        if (a.overview.one_sentence_explanation or a.overview.reading_strategy
                or a.overview.sentence_type or a.overview.difficulty_reason):
            self._v.addWidget(self._overview_card(a))

        # 阅读建议（顶部小卡）
        if a.reading_tips:
            tips = Card("阅读建议")
            for tip in a.reading_tips[:5]:
                if tip.strip():
                    lbl = _plain(QLabel("· " + tip))
                    lbl.setWordWrap(True)
                    lbl.setProperty("role", "secondary")
                    tips.body().addWidget(lbl)
            self._v.addWidget(tips)

        # 深入理解
        deep = CollapsibleCard("深入理解", expanded=True)
        self._sections[SECTION_SYNTAX] = deep

        if a.syntax.structure_summary or a.syntax.segments or a.syntax.clauses or (
            a.syntax.main_clause.subject or a.syntax.main_clause.predicate
        ):
            struct = Card("句子结构")
            summary = _plain(QLabel(a.syntax.structure_summary))
            summary.setWordWrap(True)
            summary.setProperty("role", "secondary")
            if a.syntax.structure_summary:
                struct.body().addWidget(summary)
            sv = StructureView(p)
            sv.build(a.syntax)
            struct.body().addWidget(sv)
            deep.add_content(struct)

        if a.grammar_points:
            g_wrap = QWidget()
            gv = QVBoxLayout(g_wrap)
            gv.setContentsMargins(0, 0, 0, 0)
            gv.setSpacing(10)
            head = QLabel("语法")
            head.setProperty("role", "h2")
            gv.addWidget(head)
            for g in a.grammar_points[:8]:
                gv.addWidget(GrammarCard(g))
            deep.add_content(g_wrap)
            self._sections[SECTION_GRAMMAR] = g_wrap

        if a.references:
            r_wrap = QWidget()
            rv_ = QVBoxLayout(r_wrap)
            rv_.setContentsMargins(0, 0, 0, 0)
            rv_.setSpacing(10)
            head = QLabel("指代关系")
            head.setProperty("role", "h2")
            rv_.addWidget(head)
            for r in a.references[:8]:
                rv_.addWidget(ReferenceCard(r))
            deep.add_content(r_wrap)
            self._sections[SECTION_REFERENCES] = r_wrap

        deep._content.setVisible(True)
        self._v.addWidget(deep)

        # 语言学习（默认折叠）
        lang_items: list[QWidget] = []
        if a.words:
            w_wrap = QWidget()
            wv = QVBoxLayout(w_wrap)
            wv.setContentsMargins(0, 0, 0, 0)
            wv.setSpacing(10)
            head = QLabel("单词")
            head.setProperty("role", "h2")
            wv.addWidget(head)
            learn_cb = self.on_learn
            for w in a.words[:12]:
                wv.addWidget(WordCard(w, on_learn=learn_cb))  # type: ignore[arg-type]
            lang_items.append(w_wrap)
            self._sections[SECTION_WORDS] = w_wrap
        if a.phrases:
            p_wrap = QWidget()
            pv = QVBoxLayout(p_wrap)
            pv.setContentsMargins(0, 0, 0, 0)
            pv.setSpacing(10)
            head = QLabel("短语")
            head.setProperty("role", "h2")
            pv.addWidget(head)
            for ph in a.phrases[:8]:
                pv.addWidget(PhraseCard(ph, on_learn=self.on_learn))  # type: ignore[arg-type]
            lang_items.append(p_wrap)
        if a.academic_expressions:
            e_wrap = QWidget()
            ev = QVBoxLayout(e_wrap)
            ev.setContentsMargins(0, 0, 0, 0)
            ev.setSpacing(10)
            head = QLabel("学术表达")
            head.setProperty("role", "h2")
            ev.addWidget(head)
            for e in a.academic_expressions[:6]:
                ev.addWidget(AcademicExpressionCard(e))
            lang_items.append(e_wrap)
        if lang_items:
            lang = CollapsibleCard("语言学习", expanded=len(a.words) <= 4)
            for w in lang_items:
                lang.add_content(w)
            self._v.addWidget(lang)

        # 背景知识（默认折叠）
        bg_items: list[QWidget] = []
        if a.concepts:
            c_wrap = QWidget()
            cv = QVBoxLayout(c_wrap)
            cv.setContentsMargins(0, 0, 0, 0)
            cv.setSpacing(10)
            head = QLabel("专业概念")
            head.setProperty("role", "h2")
            cv.addWidget(head)
            for c in a.concepts[:6]:
                cv.addWidget(ConceptCard(c))
            bg_items.append(c_wrap)
            self._sections[SECTION_CONCEPTS] = c_wrap
        if a.misunderstandings:
            m_wrap = QWidget()
            mv = QVBoxLayout(m_wrap)
            mv.setContentsMargins(0, 0, 0, 0)
            mv.setSpacing(10)
            head = QLabel("易错理解")
            head.setProperty("role", "h2")
            mv.addWidget(head)
            for m in a.misunderstandings[:4]:
                mv.addWidget(MisunderstandingCard(m))
            bg_items.append(m_wrap)
            self._sections[SECTION_MISUNDERSTANDINGS] = m_wrap
        if bg_items:
            bg = CollapsibleCard("背景知识", expanded=False)
            for w in bg_items:
                bg.add_content(w)
            self._v.addWidget(bg)

        # 联网研究说明
        wr = a.web_research
        if wr.used:
            src_txt = "、".join(s.title or s.url for s in wr.sources[:3])
            note = _plain(QLabel(
                f"AI 联网核实了论文信息{'：' + src_txt if src_txt else ''}"
                + (f"　{wr.notes}" if wr.notes else "")
            ))
            note.setWordWrap(True)
            note.setProperty("role", "tertiary")
            self._v.addWidget(note)

        self._v.addStretch(1)

        # 原句交互
        self.sentence_widget.set_analysis(a.source_text, a.syntax.segments, a.syntax.clauses, word_color_map)
        self.sentence_widget.segment_clicked.connect(self._scroll_to_segment)

    # ------------------------------------------------------------------
    def _overview_card(self, a: PaperAnalysis) -> QWidget:
        from paperlingo.ui.widgets.common import OverviewCard

        return OverviewCard(a.overview)

    def clear(self) -> None:
        while self._v.count():
            item = self._v.takeAt(0)
            w = item.widget()
            if w is self.sentence_widget:
                continue
            if w:
                w.setParent(None)
                w.deleteLater()
        self._sections.clear()
        # sentence widget 永远在顶部
        self._v.insertWidget(0, self.sentence_widget)

    def scroll_to_section(self, key: str) -> None:
        w = self._sections.get(key)
        if w:
            self.ensureWidgetVisible(w, 0, 100)

    def _scroll_to_segment(self, role: str, text: str) -> None:
        # 单词 -> 单词区；从句/角色 -> 结构区
        if role == "单词":
            self.scroll_to_section(SECTION_WORDS)
        else:
            self.scroll_to_section(SECTION_SYNTAX)
