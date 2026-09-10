"""句子结构视图：主干行 + 分段色块 + 从句树。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from paperlingo.domain.analysis import Syntax

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


class _SegmentChip(QFrame):
    """一个语法片段色块：原文 + 角色标签。"""

    def __init__(self, text: str, role_zh: str, color_key: str, palette,
                 explanation: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        color = getattr(palette, color_key)
        self.setToolTip(f"{role_zh}\n{text}" + (f"\n——\n{explanation}" if explanation else ""))
        self.setCursor(Qt.CursorShape.WhatsThisCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(2)
        t = QLabel(text)
        t.setWordWrap(True)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet(f"color: {color}; font-weight: 600; font-size: 13px; background: transparent;")
        lay.addWidget(t)
        r = QLabel(role_zh)
        r.setAlignment(Qt.AlignmentFlag.AlignCenter)
        r.setStyleSheet(
            f"color: {color}; font-size: 11px; background: transparent;"
        )
        lay.addWidget(r)
        self.setStyleSheet(
            f"QFrame {{ background: {color}14; border: 1px solid {color}40;"
            f" border-radius: 8px; }}"
        )


class StructureView(QWidget):
    """结构总览：主干 + 片段流式排列 + 从句列表。"""

    def __init__(self, palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._palette = palette
        self._v = QVBoxLayout(self)
        self._v.setContentsMargins(0, 0, 0, 0)
        self._v.setSpacing(12)

    def build(self, syntax: Syntax) -> None:
        while self._v.count():
            item = self._v.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        p = self._palette
        # 主干
        mc = syntax.main_clause
        if mc.subject or mc.predicate or mc.object:
            row = QFrame()
            row.setProperty("role", "inset")
            rv = QVBoxLayout(row)
            rv.setContentsMargins(14, 10, 14, 10)
            rv.setSpacing(6)
            head = QLabel("句子主干")
            head.setProperty("role", "tertiary")
            rv.addWidget(head)
            flow = QHBoxLayout()
            flow.setSpacing(8)
            for text, role in (
                (mc.subject, "subject"),
                (mc.predicate, "predicate"),
                (mc.object, "object"),
                (mc.complement, "complement"),
            ):
                if not text.strip():
                    continue
                flow.addWidget(_SegmentChip(text, "", _ROLE_COLORS[role], p))
                plus = QLabel("＋")
                plus.setProperty("role", "tertiary")
                flow.addWidget(plus)
            if flow.count():
                flow.takeAt(flow.count() - 1)  # 去掉最后一个 +
            flow.addStretch(1)
            rv.addLayout(flow)
            if mc.summary_zh:
                s = QLabel(mc.summary_zh)
                s.setWordWrap(True)
                s.setProperty("role", "secondary")
                rv.addWidget(s)
            self._v.addWidget(row)

        # 片段流
        if syntax.segments:
            seg_frame = QFrame()
            seg_frame.setProperty("role", "inset")
            sv = QVBoxLayout(seg_frame)
            sv.setContentsMargins(14, 10, 14, 10)
            sv.setSpacing(8)
            head = QLabel("逐段拆解")
            head.setProperty("role", "tertiary")
            sv.addWidget(head)
            # 流式：每行最多 3 个 chip
            row_lay: QHBoxLayout | None = None
            count_in_row = 0
            for seg in syntax.segments:
                if not seg.text.strip():
                    continue
                if row_lay is None or count_in_row >= 3:
                    row_lay = QHBoxLayout()
                    row_lay.setSpacing(8)
                    sv.addLayout(row_lay)
                    count_in_row = 0
                color_key = _ROLE_COLORS.get(seg.role.lower(), "role_misc")
                role_zh = seg.role_zh or seg.role
                row_lay.addWidget(_SegmentChip(seg.text, role_zh, color_key, p, seg.explanation), 1)
                count_in_row += 1
            self._v.addWidget(seg_frame)

        # 从句树
        if syntax.clauses:
            cl_frame = QFrame()
            cl_frame.setProperty("role", "inset")
            cv = QVBoxLayout(cl_frame)
            cv.setContentsMargins(14, 10, 14, 10)
            cv.setSpacing(8)
            head = QLabel("从句与修饰")
            head.setProperty("role", "tertiary")
            cv.addWidget(head)
            for c in syntax.clauses:
                if not c.text.strip():
                    continue
                item = QVBoxLayout()
                item.setSpacing(2)
                top_row = QHBoxLayout()
                type_lbl = QLabel(c.type_zh or c.type)
                type_lbl.setStyleSheet(
                    f"color: {p.role_clause}; font-weight: 600; font-size: 12px;"
                    "background: transparent;"
                )
                top_row.addWidget(type_lbl)
                if c.modifies:
                    mod = QLabel(f"修饰：{c.modifies}")
                    mod.setProperty("role", "tertiary")
                    mod.setWordWrap(True)
                    top_row.addWidget(mod)
                    top_row.addStretch(1)
                item.addLayout(top_row)
                text_lbl = QLabel(c.text)
                text_lbl.setWordWrap(True)
                text_lbl.setStyleSheet("font-family: 'Segoe UI'; background: transparent;")
                item.addWidget(text_lbl)
                if c.explanation:
                    exp = QLabel(c.explanation)
                    exp.setWordWrap(True)
                    exp.setProperty("role", "secondary")
                    item.addWidget(exp)
                cv.addLayout(item)
            self._v.addWidget(cl_frame)

        if self._v.count() == 0 and not syntax.structure_summary:
            empty = QLabel("AI 未返回结构信息")
            empty.setProperty("role", "tertiary")
            self._v.addWidget(empty)
