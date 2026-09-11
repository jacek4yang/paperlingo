"""Interactive structure explorer: clickable segment chips + detail panel.

A segment chip is one meaningful structural unit (subject / predicate / object /
complement / modifier / clause / connector ...). Default text stays neutral;
hover is subtle; the selected chip gets one accent treatment. Clicking a chip
fills the dedicated detail area (English segment, Chinese role, what it does,
what it modifies, how to read it). Meaning is never carried by color alone —
every chip shows its role label as text.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from paperlingo.domain.analysis import Clause, Syntax, SyntaxSegment
from paperlingo.ui.strings_zh_cn import (
    CLAUSE_TYPE_LABEL,
    CLAUSES_LABEL,
    SEGMENT_FUNCTION_LABEL,
    SEGMENT_MODIFIES_LABEL,
    SEGMENT_ROLE_LABEL,
    SEGMENT_TEXT_LABEL,
)
from paperlingo.ui.widgets.common import _plain
from paperlingo.ui.widgets.list_detail import detail_label

#: English role -> palette color key (kept in one place)
_ROLE_COLORS = {
    "subject": "role_subject",
    "predicate": "role_predicate",
    "verb": "role_predicate",
    "object": "role_object",
    "complement": "role_object",
    "attributive": "role_modifier",
    "adverbial": "role_modifier",
    "modifier": "role_modifier",
    "clause": "role_clause",
    "appositive": "role_misc",
    "parenthesis": "role_misc",
    "connector": "role_misc",
}


class _SegmentChip(QPushButton):
    """One clickable structural segment (checkable)."""

    def __init__(self, seg: SyntaxSegment, parent: QWidget | None = None) -> None:
        super().__init__(seg.text, parent)
        self.segment = seg
        self.color_key = _ROLE_COLORS.get(seg.role.lower(), "role_misc")
        self.role_zh = seg.role_zh or seg.role
        self.setProperty("role", "segchip")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{self.role_zh}\n{seg.text}")
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)


def _meta_line(title: str, body: str) -> QWidget:
    """A small labeled field used inside the detail panel."""
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(2)
    head = QLabel(title)
    head.setProperty("role", "tertiary")
    v.addWidget(head)
    v.addWidget(detail_label(body if body.strip() else "—"))
    return w


class SegmentExplorer(QWidget):
    """Structure tab content: skeleton, segment chips, clause list, detail."""

    def __init__(self, palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._palette = palette
        self._group: QButtonGroup | None = None
        self._syntax: Syntax | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        # Sentence skeleton (plain text from the AI, not color-coded)
        self._skeleton_box = QFrame()
        self._skeleton_box.setProperty("role", "inset")
        self._skeleton_v = QVBoxLayout(self._skeleton_box)
        self._skeleton_v.setContentsMargins(14, 10, 14, 10)
        self._skeleton_v.setSpacing(6)
        outer.addWidget(self._skeleton_box)

        # Chips area
        self._chips_area = QScrollArea()
        self._chips_area.setWidgetResizable(True)
        self._chips_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self._chips_area.setMaximumHeight(260)
        self._chips_host = QWidget()
        self._chips_v = QVBoxLayout(self._chips_host)
        self._chips_v.setContentsMargins(0, 0, 0, 0)
        self._chips_v.setSpacing(8)
        self._chips_area.setWidget(self._chips_host)
        outer.addWidget(self._chips_area)

        # Detail panel
        self._detail_box = QFrame()
        self._detail_box.setProperty("role", "card")
        self._detail_v = QVBoxLayout(self._detail_box)
        self._detail_v.setContentsMargins(16, 12, 16, 12)
        self._detail_v.setSpacing(8)
        outer.addWidget(self._detail_box, 1)

    # ------------------------------------------------------------------
    def build(self, syntax: Syntax) -> None:
        self._syntax = syntax

        # Skeleton
        _clear_layout(self._skeleton_v)
        mc = syntax.main_clause
        if syntax.skeleton or mc.subject or mc.predicate or mc.object:
            head = QLabel("句子主干")
            head.setProperty("role", "tertiary")
            self._skeleton_v.addWidget(head)
            if syntax.skeleton:
                self._skeleton_v.addWidget(detail_label(syntax.skeleton))
            parts = [t for t in (mc.subject, mc.predicate, mc.object, mc.complement) if t.strip()]
            if parts:
                self._skeleton_v.addWidget(detail_label("＋".join(parts)))
            if mc.summary_zh:
                self._skeleton_v.addWidget(detail_label(mc.summary_zh, "secondary"))
            self._skeleton_box.show()
        else:
            self._skeleton_box.hide()

        # Chips
        _clear_layout(self._chips_v)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        chips: list[_SegmentChip] = []
        row: QHBoxLayout | None = None
        count_in_row = 0
        for seg in syntax.segments:
            if not seg.text.strip():
                continue
            chip = _SegmentChip(seg)
            self._group.addButton(chip)
            chips.append(chip)
            if row is None or count_in_row >= 3:
                row = QHBoxLayout()
                row.setSpacing(8)
                self._chips_v.addLayout(row)
                count_in_row = 0
            row.addWidget(chip, 1)
            count_in_row += 1
        for chip in chips:
            chip.clicked.connect(lambda _=False, c=chip: self._show_detail(c))

        if not chips:
            empty = QLabel("AI 未返回可交互的片段")
            empty.setProperty("role", "tertiary")
            self._chips_v.addWidget(empty)

        # Clause list
        clauses = [c for c in syntax.clauses if c.text.strip()]
        if clauses:
            box = QFrame()
            box.setProperty("role", "inset")
            cv = QVBoxLayout(box)
            cv.setContentsMargins(14, 10, 14, 10)
            cv.setSpacing(8)
            head2 = QLabel(CLAUSES_LABEL)
            head2.setProperty("role", "tertiary")
            cv.addWidget(head2)
            for c in clauses:
                cv.addWidget(self._clause_item(c))
            self._chips_v.addWidget(box)

        self._chips_v.addStretch(1)

        # Detail panel: select the first chip by default
        self._clear_detail()
        if chips:
            chips[0].setChecked(True)
            self._show_detail(chips[0])

    # ------------------------------------------------------------------
    def _clause_item(self, c: Clause) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        top = QHBoxLayout()
        type_lbl = _plain(QLabel(f"{CLAUSE_TYPE_LABEL}：{c.type_zh or c.type}"))
        type_lbl.setProperty("role", "secondary")
        top.addWidget(type_lbl)
        if c.modifies:
            mod = _plain(QLabel(f"{SEGMENT_MODIFIES_LABEL}：{c.modifies}"))
            mod.setProperty("role", "tertiary")
            mod.setWordWrap(True)
            top.addWidget(mod)
            top.addStretch(1)
        v.addLayout(top)
        v.addWidget(detail_label(c.text))
        if c.explanation:
            v.addWidget(detail_label(c.explanation, "secondary"))
        return w

    def _clear_detail(self) -> None:
        _clear_layout(self._detail_v)

    def _show_detail(self, chip: _SegmentChip) -> None:
        seg = chip.segment
        self._clear_detail()
        title = QLabel(SEGMENT_TEXT_LABEL)
        title.setProperty("role", "h2")
        self._detail_v.addWidget(title)

        # English segment (prominent; source text should read easily)
        src = detail_label(seg.text)
        src.setStyleSheet("font-size: 16px; font-weight: 600;")
        self._detail_v.addWidget(src)

        self._detail_v.addWidget(_meta_line(SEGMENT_ROLE_LABEL, chip.role_zh))
        if seg.explanation.strip():
            self._detail_v.addWidget(_meta_line(SEGMENT_FUNCTION_LABEL, seg.explanation))
        modifies = self._find_modifies(seg)
        if modifies:
            self._detail_v.addWidget(_meta_line(SEGMENT_MODIFIES_LABEL, modifies))

    def _find_modifies(self, seg: SyntaxSegment) -> str:
        """Best-effort 'what it modifies' from matching clause metadata; empty
        when the AI gave nothing usable (never fabricated)."""
        if self._syntax is None:
            return ""
        for c in self._syntax.clauses:
            if c.modifies.strip() and c.text.strip() and (
                seg.text.strip() in c.text or c.text in seg.text
            ):
                return c.modifies
        return ""


def _clear_layout(layout: QVBoxLayout) -> None:
    """Remove all widgets and child layouts (nested row layouts included)."""
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
            continue
        child = item.layout()
        if child is not None:
            _clear_layout(child)  # type: ignore[arg-type]
            child.deleteLater()


def build_structure_scroll(palette, syntax: Syntax) -> tuple[QScrollArea, SegmentExplorer]:
    """Create the structure page: a SegmentExplorer inside a scroll area."""
    explorer = SegmentExplorer(palette)
    explorer.build(syntax)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setWidget(explorer)
    return scroll, explorer
