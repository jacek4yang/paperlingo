"""Knowledge-base page: words / phrases / grammar / expressions / concepts tabs
plus sentence patterns."""

from __future__ import annotations

import json
from html import escape
from typing import ClassVar

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from paperlingo.database.repository import Repository
from paperlingo.domain.learning import MasteryStatus
from paperlingo.ui.widgets.common import EmptyState, LearningStatusButtons

_TABS = ["单词", "短语", "语法", "学术表达", "概念", "句型"]


def _status_badge(status: str) -> str:
    if status == "known":
        return "　已掌握"
    if status == "unfamiliar":
        return "　不熟"
    if status == "hard":
        return "　不会"
    return ""


class KnowledgePage(QWidget):
    def __init__(self, repo: Repository, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.repo = repo
        self._setup_ui()

    def _setup_ui(self) -> None:
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(12)

        title = QLabel("知识库")
        title.setProperty("role", "title")
        v.addWidget(title)

        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索单词、短语、语法……")
        self.search_edit.setProperty("role", "search")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search)
        search_row.addWidget(self.search_edit, 1)
        v.addLayout(search_row)

        self.tabs = QTabWidget()
        v.addWidget(self.tabs, 1)

        hint = QLabel("双击条目查看详情，可标记掌握程度")
        hint.setProperty("role", "tertiary")
        v.addWidget(hint)

        self._lists: dict[str, QListWidget] = {}
        for name in _TABS:
            lw = QListWidget()
            lw.setWordWrap(True)
            lw.itemDoubleClicked.connect(self._open_detail)
            self.tabs.addTab(lw, name)
            self._lists[name] = lw

        self.empty = EmptyState(
            "知识库还是空的", "分析论文时遇到的单词、短语、语法会自动沉淀到这里"
        )
        v.addWidget(self.empty)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        search = self.search_edit.text().strip()
        self._fill_words(search)
        self._fill_phrases(search)
        self._fill_grammar(search)
        self._fill_expressions(search)
        self._fill_concepts(search)
        self._fill_patterns()
        has = any(lw.count() for lw in self._lists.values())
        self.empty.setVisible(not has)
        self.tabs.setVisible(has)
        self.search_edit.parentWidget().setVisible(True)

    def _on_search(self) -> None:
        self.refresh()

    def _add_status_row(self, lw: QListWidget, main: str, sub: str, detail: dict) -> None:
        text = f"{main}{_status_badge(detail.get('status', ''))}\n{sub}"
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, detail)
        lw.addItem(item)

    def _fill_words(self, search: str) -> None:
        lw = self._lists["单词"]
        lw.clear()
        for r in self.repo.list_words(search=search):
            sub = f"出现 {r.occurrences} 次 · 来自 {r.analyses_count} 篇分析 · {r.pos}"
            self._add_status_row(lw, r.lemma, sub, {"kind": "word", "id": r.word_id})

    def _fill_phrases(self, search: str) -> None:
        lw = self._lists["短语"]
        lw.clear()
        for r in self.repo.list_phrases(search=search):
            meaning = r.meanings[0] if r.meanings else ""
            self._add_status_row(
                lw, r.text, f"{meaning}　·　出现 {r.occurrences} 次",
                {"kind": "phrase", "id": r.phrase_id},
            )

    def _fill_grammar(self, search: str) -> None:
        lw = self._lists["语法"]
        lw.clear()
        for r in self.repo.list_grammar(search=search):
            name = r.name_zh or r.name
            self._add_status_row(
                lw, name, f"{r.name}　·　出现 {r.occurrences} 次",
                {"kind": "grammar", "id": r.grammar_id},
            )

    def _fill_expressions(self, search: str) -> None:
        lw = self._lists["学术表达"]
        lw.clear()
        for r in self.repo.list_expressions(search=search):
            self._add_status_row(
                lw, r.text, r.meaning or "", {"kind": "expression", "id": r.expr_id}
            )

    def _fill_concepts(self, search: str) -> None:
        lw = self._lists["概念"]
        lw.clear()
        for r in self.repo.list_concepts(search=search):
            title = r.term + (f"（{r.translation}）" if r.translation else "")
            self._add_status_row(
                lw, title, (r.simple_explanation or "")[:60],
                {"kind": "concept", "id": r.concept_id},
            )

    def _fill_patterns(self) -> None:
        lw = self._lists["句型"]
        lw.clear()
        for p in self.repo.list_sentence_patterns():
            skeleton = p.get("skeleton") or ""
            text = p["structure_summary"] + (f"\n{skeleton}" if skeleton else "")
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, {"kind": "pattern", "id": p["id"]})
            lw.addItem(item)

    # ------------------------------------------------------------------
    def _open_detail(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        dlg = _DetailDialog(self.repo, data, self)
        dlg.exec()


class _DetailDialog(QDialog):
    """Item detail dialog. Every string entering the HTML (AI / database
    content) must be escaped."""

    #: Per-kind hint at the top of the dialog, clarifying what each category
    #: is for (avoids phrase/grammar/expression looking redundant).
    _KIND_HINTS: ClassVar[dict[str, str]] = {
        "word": "这个词在论文里的意思和用法",
        "phrase": "值得整组记忆的词组搭配",
        "grammar": "值得学会识别和模仿的句子结构",
        "expression": "论文写作中可以主动使用的表达",
        "concept": "论文涉及的专业概念",
    }

    def __init__(self, repo: Repository, data: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.repo = repo
        self.data = data
        kind, ref_id = data["kind"], data["id"]
        titles = {"word": "单词详情", "phrase": "短语详情", "grammar": "语法详情",
                  "expression": "学术表达", "concept": "概念详情", "pattern": "句型"}
        self.setWindowTitle(titles.get(kind, "详情"))
        self.resize(560, 520)
        v = QVBoxLayout(self)
        self._browser = QTextBrowser()
        self._browser.setFrameShape(QTextBrowser.Shape.NoFrame)
        self._browser.setOpenLinks(False)  # not a browser: never auto-open links
        v.addWidget(self._browser, 1)

        # Mastery-status buttons (not for sentence patterns)
        self._status_row = QHBoxLayout()
        v.addLayout(self._status_row)
        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        v.addLayout(row)

        self._item_type = kind if kind in ("word", "phrase", "grammar", "expression", "concept") else None
        self._ref_id = ref_id
        self._render(kind, ref_id)
        if self._item_type:
            li = repo.get_learning_item(self._item_type, ref_id)
            current = MasteryStatus(li["status"]) if li else MasteryStatus.UNKNOWN

            def on_change(s: MasteryStatus) -> None:
                repo.set_mastery(self._item_type, self._ref_id, s)  # type: ignore[arg-type]

            self._status_row.addWidget(QLabel("掌握程度"))
            self._status_row.addWidget(LearningStatusButtons(current, on_change))
            self._status_row.addStretch(1)

    def _render(self, kind: str, ref_id: int) -> None:
        dispatch = {
            "word": self._render_word,
            "phrase": self._render_phrase,
            "grammar": self._render_grammar,
            "expression": self._render_expression,
            "concept": self._render_concept,
            "pattern": self._render_pattern,
        }
        fn = dispatch.get(kind)
        if fn is None:
            self._browser.setPlainText("（无详细信息）")
            return
        fn(ref_id)
        hint = self._KIND_HINTS.get(kind)
        if hint:
            self._browser.append(f"<p style='color:#999'>{escape(hint)}</p>")

    def _render_word(self, wid: int) -> None:
        detail = self.repo.get_word_detail(wid)
        if not detail:
            self._browser.setPlainText("（已删除）")
            return
        w = detail["word"]
        occ = detail["occurrences"]
        lines = [
            f"<h2>{escape(w['lemma'])}</h2>",
            f"<p style='color:#888'>{escape(w['pos'] or '')}</p>",
        ]
        meanings: list[str] = []
        for o in occ:
            if o["meaning_in_context"] and o["meaning_in_context"] not in meanings:
                meanings.append(o["meaning_in_context"])
        if meanings:
            lines.append("<h3>本句中的含义</h3>")
            for i, m in enumerate(meanings, 1):
                lines.append(f"<p>{i}. {escape(m)}</p>")
        first = occ[0] if occ else {}
        if first.get("academic_meaning"):
            lines.append(f"<p><b>学术语境：</b>{escape(first['academic_meaning'])}</p>")
        if first.get("collocations_json") and first["collocations_json"] != "[]":
            try:
                cols = json.loads(first["collocations_json"])
            except (ValueError, TypeError):
                cols = []
            if cols:
                lines.append(
                    "<p><b>常见搭配：</b>" + "　".join(escape(c) for c in cols) + "</p>"
                )
        lines.append(f"<p style='color:#888'>共出现 {len(occ)} 次</p>")
        self._browser.setHtml("".join(lines))

    def _render_phrase(self, pid: int) -> None:
        detail = self.repo.get_phrase_detail(pid)
        if not detail:
            self._browser.setPlainText("（已删除）")
            return
        lines = [f"<h2>{escape(detail['text'])}</h2>"]
        seen: set[str] = set()
        for r in detail["occurrences"]:
            if r["meaning"] in seen:
                continue
            seen.add(r["meaning"])
            lines.append(f"<p><b>{escape(r['meaning'])}</b></p>")
            if r["explanation"]:
                lines.append(f"<p>{escape(r['explanation'])}</p>")
            if r["example"]:
                lines.append(
                    f"<p style='color:#888'>{escape(r['example'])}　{escape(r['example_zh'] or '')}</p>"
                )
        self._browser.setHtml("".join(lines))

    def _render_grammar(self, gid: int) -> None:
        detail = self.repo.get_grammar_detail(gid)
        if not detail:
            self._browser.setPlainText("（已删除）")
            return
        lines = [
            f"<h2>{escape(detail['name_zh'] or detail['name'])}</h2>",
            f"<p style='color:#888'>{escape(detail['name'])}</p>",
        ]
        for r in detail["occurrences"][:1]:
            if r["source"]:
                lines.append(f"<p style='color:#888'>出处：{escape(r['source'])}</p>")
            if r["explanation"]:
                lines.append(f"<p>{escape(r['explanation'])}</p>")
            if r["why_used_here"]:
                lines.append(f"<p><b>为什么这里这样用：</b>{escape(r['why_used_here'])}</p>")
            if r["common_mistake"]:
                lines.append(f"<p style='color:#c66'><b>常见误解：</b>{escape(r['common_mistake'])}</p>")
            if r["simple_example"]:
                lines.append(
                    f"<p>例：{escape(r['simple_example'])}　{escape(r['simple_example_zh'] or '')}</p>"
                )
        self._browser.setHtml("".join(lines))

    def _render_expression(self, eid: int) -> None:
        r = self.repo.get_expression_detail(eid)
        if not r:
            self._browser.setPlainText("（已删除）")
            return
        html = f"<h2>{escape(r['text'])}</h2><p><b>{escape(r['meaning'] or '')}</b></p>"
        if r["usage"]:
            html += f"<p>{escape(r['usage'])}</p>"
        if r["when_to_use"]:
            html += f"<p><b>什么时候用：</b>{escape(r['when_to_use'])}</p>"
        if r["example"]:
            html += f"<p style='color:#888'>{escape(r['example'])}　{escape(r['example_zh'] or '')}</p>"
        self._browser.setHtml(html)

    def _render_concept(self, cid: int) -> None:
        r = self.repo.get_concept_detail(cid)
        if not r:
            self._browser.setPlainText("（已删除）")
            return
        title = r["term"] + (f"（{r['translation']}）" if r["translation"] else "")
        html = f"<h2>{escape(title)}</h2><p>{escape(r['simple_explanation'] or '')}</p>"
        if r["meaning_in_this_paper"]:
            html += f"<p><b>在本文中：</b>{escape(r['meaning_in_this_paper'])}</p>"
        self._browser.setHtml(html)

    def _render_pattern(self, pid: int) -> None:
        r = self.repo.get_sentence_pattern(pid)
        if not r:
            self._browser.setPlainText("（已删除）")
            return
        html = f"<h2>{escape(r['structure_summary'])}</h2>"
        if r["skeleton"]:
            html += f"<p style='color:#888'>{escape(r['skeleton'])}</p>"
        self._browser.setHtml(html)
