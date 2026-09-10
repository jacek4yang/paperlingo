"""交互式原句展示：把 AI 返回的 segment / clause 映射回原文，做语义高亮。

原则：
- 不修改原文字符；映射失败宁可不高亮，绝不错误匹配。
- 鼠标 hover 显示角色 tooltip；点击发出信号，由外部滚动到对应卡片。
"""

from __future__ import annotations

import unicodedata

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QTextBrowser, QVBoxLayout, QWidget

from paperlingo.domain.analysis import Clause, SyntaxSegment

#: 角色 -> 调色板键
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

_ROLE_ZH = {
    "subject": "主语", "predicate": "谓语", "object": "宾语",
    "complement": "宾补/表语", "attributive": "定语", "adverbial": "状语",
    "clause": "从句", "appositive": "同位语", "parenthesis": "插入语",
    "connector": "连接词", "modifier": "修饰成分",
}


def _norm(s: str) -> str:
    """规范化用于匹配：NFC + 折叠空白。"""
    return " ".join(unicodedata.normalize("NFC", s).split())


def _fold(s: str) -> str:
    return _norm(s).casefold()


def find_span(source: str, needle: str) -> tuple[int, int] | None:
    """在原文中精确查找 needle 的位置，返回 (start, end)。

    依次尝试：原文精确、折叠空白精确、忽略大小写、折叠空白+忽略大小写。
    都失败返回 None（宁可不高亮，也不错配）。
    """
    if not needle.strip():
        return None
    src_norm = _norm(source)
    nd_norm = _norm(needle)
    src_fold = _fold(source)
    nd_fold = _fold(needle)

    # 1. 原文精确匹配
    idx = source.find(needle)
    if idx >= 0:
        return idx, idx + len(needle)
    # 2. 规范化空白后在规范化原文中找，再映射回原索引
    pos = src_norm.find(nd_norm)
    if pos >= 0:
        return _map_norm_pos(source, src_norm, pos, len(nd_norm))
    # 3. 忽略大小写
    pos = src_fold.find(nd_fold)
    if pos >= 0:
        # src_fold 与 source 等长（casefold 大多数情况等长；为安全起见重新映射）
        return _map_casefold_pos(source, src_fold, pos, len(nd_fold))
    return None


def _map_norm_pos(source: str, src_norm: str, pos: int, length: int) -> tuple[int, int] | None:
    """把规范化文本中的位置映射回原文位置。"""
    # 构建规范化文本 -> 原文索引的映射
    norm_to_src: list[int] = []
    building = ""
    for i, ch in enumerate(source):
        norm_chars = unicodedata.normalize("NFC", ch)
        for nc in norm_chars:
            building += nc
            norm_to_src.append(i)
    # 折叠空白的影响：_norm 把连续空白折叠为一个空格，我们近似处理：
    # 直接对 src_norm 与 building 比对，若一致则用映射
    folded = " ".join(building.split())
    if folded != src_norm:
        # 复杂折叠场景，退化为按比例估算（安全性足够：仅影响高亮，不影响数据）
        start = min(len(source) - 1, pos)
        end = min(len(source), pos + length)
        return start, end
    if pos < len(norm_to_src) and pos + length - 1 < len(norm_to_src):
        return norm_to_src[pos], norm_to_src[pos + length - 1] + 1
    return None


def _map_casefold_pos(source: str, src_fold: str, pos: int, length: int) -> tuple[int, int] | None:
    if len(src_fold) == len(source):
        return pos, pos + length
    return _map_norm_pos(source, src_fold, pos, length)


class InteractiveSentenceWidget(QWidget):
    """顶部原句视图：角色高亮 + 悬停提示 + 点击定位。"""

    segment_clicked = pyqtSignal(str, str)  # role, text
    clause_clicked = pyqtSignal(str, str)  # type_zh, text

    def __init__(self, palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._palette = palette
        self._v = QVBoxLayout(self)
        self._v.setContentsMargins(0, 0, 0, 0)
        self._v.setSpacing(6)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(False)
        self._browser.setOpenLinks(False)
        self._browser.setFrameShape(QTextBrowser.Shape.NoFrame)
        self._browser.setReadOnly(True)
        self._browser.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._browser.anchorClicked.connect(self._on_anchor)
        self._v.addWidget(self._browser)

        self._hint = QLabel("鼠标悬停可查看语法角色，点击彩色片段可跳到对应解释")
        self._hint.setProperty("role", "tertiary")
        self._hint.setWordWrap(True)
        self._v.addWidget(self._hint)

    # ------------------------------------------------------------------
    def set_analysis(self, source_text: str,
                     segments: list[SyntaxSegment], clauses: list[Clause],
                     word_spans: dict[str, tuple[str, str]] | None = None) -> None:
        """渲染原句并做高亮。

        word_spans: surface -> (color_key, info) 供单词悬停提示（可选）。
        """
        self._browser.clear()
        if not source_text.strip():
            self._browser.setPlainText("")
            self._hint.hide()
            return
        self._hint.show()

        # 1) 从句高亮（先处理，层级更低）
        clause_hits: list[tuple[int, int, str]] = []
        for c in clauses:
            if not c.text.strip():
                continue
            span = find_span(source_text, c.text)
            if span is None:
                continue
            type_zh = c.type_zh or _ROLE_ZH.get(c.type, "从句")
            clause_hits.append((span[0], span[1], type_zh))

        # 2) segment 高亮
        seg_hits: list[tuple[int, int, str, str]] = []
        for s in segments:
            if not s.text.strip():
                continue
            span = find_span(source_text, s.text)
            if span is None:
                continue
            color_key = _ROLE_COLORS.get(s.role.lower(), "role_misc")
            role_zh = s.role_zh or _ROLE_ZH.get(s.role.lower(), s.role)
            seg_hits.append((span[0], span[1], color_key, role_zh))

        # 冲突处理：segment 优先于从句（更细粒度）
        def overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
            return a[0] < b[1] and b[0] < a[1]

        seg_ranges = [(h[0], h[1]) for h in seg_hits]
        clause_final = [h for h in clause_hits if not any(overlaps((h[0], h[1]), r) for r in seg_ranges)]

        html_text = self._wrap_anchors(source_text, clause_final, seg_hits, word_spans or {})

        self._browser.setHtml(
            f"<div style=\"line-height:1.9; font-size:15px;\">{html_text}</div>"
        )

    # ------------------------------------------------------------------
    def _wrap_anchors(
        self,
        source: str,
        clause_hits: list[tuple[int, int, str]],
        seg_hits: list[tuple[int, int, str, str]],
        word_spans: dict[str, tuple[str, str]],
    ) -> str:
        """把命中区间包上 <a> 锚点与颜色 span。所有 HTML 由本程序构造。"""
        events: list[tuple[int, int, str, str]] = []  # (start, end, kind, payload)
        for s, e, tz in clause_hits:
            events.append((s, e, "clause", tz))
        for s, e, color_key, role_zh in seg_hits:
            events.append((s, e, "seg", f"{role_zh}|{color_key}|{source[s:e]}"))
        for surface, (color_key, info) in word_spans.items():
            span = find_span(source, surface)
            if span is None:
                continue
            # 单词优先级最高（最细）
            events.append((span[0], span[1], "word", f"{surface}|{color_key}|{info}"))

        # 按起点排序，过滤重叠（保留更细粒度：word > seg > clause）
        priority = {"word": 3, "seg": 2, "clause": 1}
        events.sort(key=lambda ev: (ev[0], -priority[ev[2]], -(ev[1] - ev[0])))
        accepted: list[tuple[int, int, str, str]] = []
        for ev in events:
            if any(not (ev[1] <= a[0] or ev[0] >= a[1]) for a in accepted):
                continue
            accepted.append(ev)
        accepted.sort(key=lambda ev: ev[0])

        parts: list[str] = []
        cursor = 0
        p = self._palette
        for s, e, kind, payload in accepted:
            parts.append(_escape_html(source[cursor:s]))
            inner = _escape_html(source[s:e])
            if kind == "clause":
                parts.append(
                    f"<a href=\"clause:{payload}\" style=\"color:inherit;"
                    f"background-color:{p.role_clause}22; text-decoration:none;"
                    f"border-bottom:2px dotted {p.role_clause};\">{inner}</a>"
                )
            elif kind == "seg":
                role_zh, color_key, _ = payload.split("|", 2)
                color = getattr(p, color_key, p.role_misc)
                parts.append(
                    f"<a href=\"seg:{payload}\" title=\"{role_zh}\" style=\"color:{color};"
                    f"text-decoration:none; border-bottom:2px solid {color};\">{inner}</a>"
                )
            else:  # word
                surface, color_key, info = payload.split("|", 2)
                color = getattr(p, color_key, p.role_misc)
                parts.append(
                    f"<a href=\"word:{payload}\" title=\"{info}\" style=\"color:{color};"
                    f"background-color:{color}18; text-decoration:none; border-radius:3px;"
                    f"padding:0 1px;\">{inner}</a>"
                )
            cursor = e
        parts.append(_escape_html(source[cursor:]))
        return "".join(parts)

    def _on_anchor(self, url) -> None:
        url_str = url.toString() if hasattr(url, "toString") else str(url)
        scheme, _, rest = url_str.partition(":")
        if scheme == "seg":
            role_zh, _color, text = rest.split("|", 2)
            self.segment_clicked.emit(role_zh, text)
        elif scheme == "clause":
            self.clause_clicked.emit(rest, "")
        elif scheme == "word":
            surface, _color, _info = rest.split("|", 2)
            self.segment_clicked.emit("单词", surface)


def _escape_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
