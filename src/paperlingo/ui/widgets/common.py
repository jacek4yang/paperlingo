"""通用小组件：卡片、按钮、空状态、错误状态、骨架屏等。"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from paperlingo.domain.learning import MasteryStatus
from paperlingo.services.clipboard import write_text


class Card(QFrame):
    """基础卡片容器：圆角白底细边框，标题 + 内容区。"""

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "card")
        self._v = QVBoxLayout(self)
        self._v.setContentsMargins(18, 14, 18, 14)
        self._v.setSpacing(10)
        self._title_label: QLabel | None = None
        if title:
            self.set_title(title)

    def set_title(self, title: str) -> None:
        if self._title_label is None:
            self._title_label = QLabel()
            self._title_label.setProperty("role", "h2")
            self._v.addWidget(self._title_label)
        self._title_label.setText(title)

    def body(self) -> QVBoxLayout:
        return self._v


def _plain(lbl: QLabel) -> QLabel:
    """强制 QLabel 按纯文本渲染。

    QLabel 默认自动检测富文本：AI 返回内容若含 <img>/<b>/<style> 等
    标签会被解释执行。所有展示 AI/用户数据的标签都必须经过这里。
    """
    lbl.setTextFormat(Qt.TextFormat.PlainText)
    return lbl


def _flow_text_label(text: str, role: str = "") -> QLabel:
    lbl = _plain(QLabel(text))
    lbl.setWordWrap(True)
    lbl.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse
    )
    if role:
        lbl.setProperty("role", role)
    return lbl


class TranslationCard(Card):
    """翻译卡片：自然翻译（大）+ 直译（小）+ 核心含义 + 译文说明。"""

    def __init__(self, natural: str, literal: str, core_meaning: str,
                 notes: list[str], parent: QWidget | None = None) -> None:
        super().__init__("翻译", parent)
        if natural:
            nat = _flow_text_label(natural)
            nat.setStyleSheet("font-size: 16px; font-weight: 600;")
            self._v.addWidget(nat)
        if core_meaning:
            self._v.addWidget(_flow_text_label(core_meaning, "secondary"))
        if literal and literal != natural:
            self._v.addWidget(_flow_text_label(f"直译：{literal}", "tertiary"))
        for note in notes[:6]:
            if note.strip():
                self._v.addWidget(_flow_text_label(f"· {note}", "tertiary"))


class OverviewCard(Card):
    """总览卡片：难度 + 句型 + 一句话解释 + 阅读策略。"""

    def __init__(self, overview, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        top = QHBoxLayout()
        top.setSpacing(10)
        diff = overview.difficulty
        badge = QLabel(f"难度 {'●' * diff}{'○' * (5 - diff)}")
        badge.setStyleSheet(
            f"color: {('#c47f17' if diff >= 4 else '#2f9e63' if diff <= 2 else '#59626d')};"
            "font-size: 12px; font-weight: 600;"
        )
        top.addWidget(badge)
        if overview.sentence_type:
            st = _plain(QLabel(overview.sentence_type))
            st.setProperty("role", "tertiary")
            top.addWidget(st)
        top.addStretch(1)
        self._v.addLayout(top)
        if overview.one_sentence_explanation:
            self._v.addWidget(_flow_text_label(overview.one_sentence_explanation))
        if overview.difficulty_reason:
            self._v.addWidget(_flow_text_label(f"为什么难：{overview.difficulty_reason}", "tertiary"))
        if overview.reading_strategy:
            box = QFrame()
            box.setProperty("role", "inset")
            bv = QVBoxLayout(box)
            bv.setContentsMargins(12, 8, 12, 8)
            lbl = _flow_text_label(f"阅读策略：{overview.reading_strategy}", "secondary")
            bv.addWidget(lbl)
            self._v.addWidget(box)


class GrammarCard(Card):
    def __init__(self, g, parent: QWidget | None = None) -> None:
        title = g.name_zh or g.name
        super().__init__(title, parent)
        if g.name and g.name_zh and g.name != g.name_zh:
            en = _plain(QLabel(g.name))
            en.setProperty("role", "tertiary")
            self._v.addWidget(en)
        if g.source:
            src = _plain(QLabel(g.source))
            src.setWordWrap(True)
            src.setStyleSheet(
                "font-family: 'Segoe UI', 'Cascadia Code', monospace; font-size: 12px;"
            )
            src.setProperty("role", "secondary")
            self._v.addWidget(src)
        if g.explanation:
            self._v.addWidget(_flow_text_label(g.explanation))
        if g.why_used_here:
            self._v.addWidget(_flow_text_label(f"在这里为什么这么用：{g.why_used_here}", "secondary"))
        if g.simple_example:
            ex = QFrame()
            ex.setProperty("role", "inset")
            ev = QVBoxLayout(ex)
            ev.setContentsMargins(12, 8, 12, 8)
            ev.setSpacing(4)
            ev.addWidget(_flow_text_label(g.simple_example))
            if g.simple_example_zh:
                ev.addWidget(_flow_text_label(g.simple_example_zh, "tertiary"))
            self._v.addWidget(ex)
        if g.common_mistake:
            self._v.addWidget(_flow_text_label(f"常见误解：{g.common_mistake}", "tertiary"))
        stars = "★" * g.importance + "☆" * (5 - g.importance)
        imp = QLabel(f"重要程度 {stars}")
        imp.setProperty("role", "tertiary")
        self._v.addWidget(imp)


class WordCard(Card):
    """单词卡片：本句含义为核心。支持「加入学习」。"""

    def __init__(self, w, parent: QWidget | None = None,
                 on_learn: Callable[[str, str, QWidget], None] | None = None) -> None:
        lemma = w.lemma or w.surface
        super().__init__(f"{w.surface or lemma}", parent)
        sub = _plain(QLabel(" · ".join(x for x in [w.lemma if w.lemma != w.surface else "", w.pos_zh or w.pos] if x)))
        if sub.text():
            sub.setProperty("role", "tertiary")
            self._v.addWidget(sub)
        if w.phonetic:
            ph = _plain(QLabel(w.phonetic))
            ph.setProperty("role", "tertiary")
            self._v.addWidget(ph)
        if w.meaning_in_context:
            box = QFrame()
            box.setProperty("role", "inset")
            bv = QVBoxLayout(box)
            bv.setContentsMargins(12, 8, 12, 8)
            bv.setSpacing(4)
            t = QLabel("本句含义")
            t.setProperty("role", "tertiary")
            bv.addWidget(t)
            m = _flow_text_label(w.meaning_in_context)
            m.setStyleSheet("font-weight: 600;")
            bv.addWidget(m)
            self._v.addWidget(box)
        if w.why_here:
            self._v.addWidget(_flow_text_label(f"为什么这样理解：{w.why_here}", "secondary"))
        if w.academic_meaning:
            self._v.addWidget(_flow_text_label(f"学术语境：{w.academic_meaning}", "secondary"))
        if w.common_meanings:
            self._v.addWidget(_flow_text_label("常见含义：" + "、".join(w.common_meanings[:5]), "tertiary"))
        if w.collocations:
            self._v.addWidget(_flow_text_label("常见搭配：" + "  ".join(w.collocations[:5]), "tertiary"))
        if on_learn is not None:
            btns = QHBoxLayout()
            btns.addStretch(1)
            known = QPushButton("我认识")
            known.setProperty("role", "ghost")
            known.clicked.connect(lambda: on_learn("word", lemma, "known"))
            learn = QPushButton("加入学习")
            learn.setProperty("role", "chip")
            learn.clicked.connect(lambda: on_learn("word", lemma, "unfamiliar"))
            btns.addWidget(known)
            btns.addWidget(learn)
            self._v.addLayout(btns)


class PhraseCard(Card):
    def __init__(self, p, parent: QWidget | None = None,
                 on_learn: Callable[[str, str, QWidget], None] | None = None) -> None:
        super().__init__(p.text, parent)
        if p.meaning:
            m = _flow_text_label(p.meaning)
            m.setStyleSheet("font-weight: 600;")
            self._v.addWidget(m)
        if p.explanation:
            self._v.addWidget(_flow_text_label(p.explanation, "secondary"))
        if p.academic_usage:
            self._v.addWidget(_flow_text_label(f"学术用法：{p.academic_usage}", "tertiary"))
        if p.example:
            ex = QFrame()
            ex.setProperty("role", "inset")
            ev = QVBoxLayout(ex)
            ev.setContentsMargins(12, 8, 12, 8)
            ev.setSpacing(4)
            ev.addWidget(_flow_text_label(p.example))
            if p.example_zh:
                ev.addWidget(_flow_text_label(p.example_zh, "tertiary"))
            self._v.addWidget(ex)
        if on_learn is not None:
            btns = QHBoxLayout()
            btns.addStretch(1)
            known = QPushButton("我认识")
            known.setProperty("role", "ghost")
            known.clicked.connect(lambda: on_learn("phrase", p.text, "known"))
            learn = QPushButton("加入学习")
            learn.setProperty("role", "chip")
            learn.clicked.connect(lambda: on_learn("phrase", p.text, "unfamiliar"))
            btns.addWidget(known)
            btns.addWidget(learn)
            self._v.addLayout(btns)


class AcademicExpressionCard(Card):
    def __init__(self, e, parent: QWidget | None = None) -> None:
        super().__init__(e.text, parent)
        if e.meaning:
            m = _flow_text_label(e.meaning)
            m.setStyleSheet("font-weight: 600;")
            self._v.addWidget(m)
        if e.usage:
            self._v.addWidget(_flow_text_label(e.usage, "secondary"))
        if e.when_to_use:
            self._v.addWidget(_flow_text_label(f"什么时候用：{e.when_to_use}", "tertiary"))
        if e.example:
            ex = _plain(QLabel(e.example + (f"　{e.example_zh}" if e.example_zh else "")))
            ex.setWordWrap(True)
            ex.setProperty("role", "tertiary")
            self._v.addWidget(ex)


class ReferenceCard(Card):
    def __init__(self, r, parent: QWidget | None = None) -> None:
        super().__init__("指代关系", parent)
        flow = QHBoxLayout()
        flow.setSpacing(10)
        expr = _plain(QLabel(r.expression))
        expr.setStyleSheet("font-family: 'Segoe UI'; font-weight: 600;")
        arrow = QLabel("↓")
        arrow.setProperty("role", "tertiary")
        refers = _plain(QLabel(r.refers_to))
        refers.setWordWrap(True)
        for w_ in (expr, arrow, refers):
            flow.addWidget(w_)
        flow.addStretch(1)
        self._v.addLayout(flow)
        if r.explanation:
            self._v.addWidget(_flow_text_label(r.explanation, "secondary"))


class ConceptCard(Card):
    def __init__(self, c, parent: QWidget | None = None) -> None:
        title = f"{c.term}" + (f"（{c.translation}）" if c.translation else "")
        super().__init__(title, parent)
        if c.simple_explanation:
            self._v.addWidget(_flow_text_label(c.simple_explanation))
        if c.meaning_in_this_paper:
            self._v.addWidget(_flow_text_label(f"在本文中：{c.meaning_in_this_paper}", "secondary"))
        if c.background_needed:
            tag = QLabel("建议补充背景知识")
            tag.setProperty("role", "tertiary")
            self._v.addWidget(tag)


class MisunderstandingCard(Card):
    def __init__(self, m, parent: QWidget | None = None) -> None:
        super().__init__("易错理解", parent)
        wrong = QFrame()
        wrong.setProperty("role", "inset")
        wv = QVBoxLayout(wrong)
        wv.setContentsMargins(12, 8, 12, 8)
        w1 = QLabel("容易误读成")
        w1.setStyleSheet("color: #d64545; font-size: 12px; font-weight: 600;")
        wv.addWidget(w1)
        wv.addWidget(_flow_text_label(m.wrong_interpretation))
        self._v.addWidget(wrong)
        if m.why_wrong:
            self._v.addWidget(_flow_text_label(f"为什么错：{m.why_wrong}", "secondary"))
        right = QFrame()
        right.setProperty("role", "inset")
        rv = QVBoxLayout(right)
        rv.setContentsMargins(12, 8, 12, 8)
        r1 = QLabel("正确理解")
        r1.setStyleSheet("color: #2f9e63; font-size: 12px; font-weight: 600;")
        rv.addWidget(r1)
        rv.addWidget(_flow_text_label(m.correct_interpretation))
        self._v.addWidget(right)


class CollapsibleCard(Card):
    """可折叠卡片：标题栏 + 展开按钮，次要内容默认折叠。"""

    def __init__(self, title: str, expanded: bool = False,
                 parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self._expanded = expanded
        self._content = QWidget()
        self._content_v = QVBoxLayout(self._content)
        self._content_v.setContentsMargins(0, 0, 0, 0)
        self._content_v.setSpacing(10)
        self._v.addWidget(self._content)

        header = QHBoxLayout()
        self._toggle = QPushButton("收起" if expanded else "展开")
        self._toggle.setProperty("role", "ghost")
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.clicked.connect(self.toggle)
        header.addStretch(1)
        header.addWidget(self._toggle)
        self._v.addLayout(header)
        self._content.setVisible(expanded)

    def toggle(self) -> None:
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        self._toggle.setText("收起" if self._expanded else "展开")

    def add_content(self, w: QWidget) -> None:
        self._content_v.addWidget(w)

    def add_content_layout(self, lay: QVBoxLayout | QHBoxLayout) -> None:
        self._content_v.addLayout(lay)


class CopyButton(QPushButton):
    """点击复制文本并短暂显示「已复制」。"""

    def __init__(self, get_text: Callable[[], str], label: str = "复制",
                 parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self._get_text = get_text
        self._orig = label
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(1600)
        self._timer.timeout.connect(self._reset)
        self.clicked.connect(self._copy)

    def _copy(self) -> None:
        try:
            write_text(self._get_text())
        except Exception:
            return
        self.setText("已复制")
        self.setEnabled(False)
        self._timer.start()

    def _reset(self) -> None:
        self.setText(self._orig)
        self.setEnabled(True)


class EmptyState(QWidget):
    """空状态：极简纯文字（主文案 + 副文案 + 可选按钮），不使用装饰图标。"""

    def __init__(self, title: str, subtitle: str = "",
                 action_text: str = "", on_action: Callable[[], None] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.setSpacing(10)
        t = QLabel(title)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setProperty("role", "title")
        v.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setAlignment(Qt.AlignmentFlag.AlignCenter)
            s.setProperty("role", "secondary")
            s.setWordWrap(True)
            v.addWidget(s)
        if action_text and on_action:
            btn = QPushButton(action_text)
            btn.setProperty("role", "primary")
            btn.clicked.connect(on_action)
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(btn)
            row.addStretch(1)
            v.addLayout(row)


class ErrorState(QWidget):
    """错误状态：标题 + 详情 + 可选操作按钮。"""

    def __init__(self, title: str, detail: str = "",
                 buttons: list[tuple[str, Callable[[], None]]] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.setSpacing(10)
        t = QLabel(title)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setProperty("role", "title")
        v.addWidget(t)
        if detail:
            d = _plain(QLabel(detail))
            d.setAlignment(Qt.AlignmentFlag.AlignCenter)
            d.setProperty("role", "secondary")
            d.setWordWrap(True)
            d.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            v.addWidget(d)
        if buttons:
            row = QHBoxLayout()
            row.addStretch(1)
            for text, cb in buttons:
                b = QPushButton(text)
                b.clicked.connect(cb)
                row.addWidget(b)
            row.addStretch(1)
            v.addLayout(row)


class SkeletonLoading(QWidget):
    """简单骨架屏：几条灰色占位条。"""

    def __init__(self, lines: int = 4, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setSpacing(12)
        v.setContentsMargins(4, 4, 4, 4)
        for i in range(lines):
            bar = QLabel()
            bar.setProperty("role", "skeleton")
            bar.setFixedHeight(16 if i else 26)
            w = [100, 85, 92, 70, 88][i % 5]
            bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            bar.setMaximumWidth(int(w * 6))
            v.addWidget(bar)
        v.addStretch(1)


class LearningStatusButtons(QWidget):
    """认识 / 不熟 / 不会 三态按钮组。"""

    def __init__(self, current: MasteryStatus,
                 on_change: Callable[[MasteryStatus], None],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self._buttons: dict[MasteryStatus, QPushButton] = {}
        self._current = current
        self._on_change = on_change
        opts = [
            (MasteryStatus.KNOWN, "认识"),
            (MasteryStatus.UNFAMILIAR, "不熟"),
            (MasteryStatus.HARD, "不会"),
        ]
        for status, label in opts:
            b = QPushButton(label)
            b.setProperty("role", "chip")
            b.setCheckable(True)
            b.setChecked(status == current)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, s=status: self._pick(s))
            lay.addWidget(b)
            self._buttons[status] = b
        self._refresh()

    def _pick(self, status: MasteryStatus) -> None:
        self._current = status
        self._refresh()
        self._on_change(status)

    def _refresh(self) -> None:
        for s, b in self._buttons.items():
            b.setChecked(s == self._current)
