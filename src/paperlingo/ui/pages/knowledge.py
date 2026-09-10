"""知识库页：单词 / 短语 / 语法 / 学术表达 / 概念 五个标签 + 句型。"""

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
    """条目详情。所有进入 HTML 的内容（来自 AI / 数据库）都必须 escape。"""

    #: 详情对话框顶部说明各类别的定位差异，避免"短语/语法/学术表达"看起来重复
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
        self._browser.setOpenLinks(False)  # 不当浏览器用：不自动打开链接
        v.addWidget(self._browser, 1)

        # 掌握状态按钮（句型除外）
        self._status_row = QHBoxLayout()
        v.addLayout(self._status_row)
        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        v.addLayout(row)

        item_type_map = {"word": "word", "phrase": "phrase", "grammar": "grammar",
                         "expression": "expression", "concept": "concept"}
        self._render(kind, ref_id)
        if kind in item_type_map:
            li = repo.get_learning_item(item_type_map[kind], ref_id)
            current = MasteryStatus(li["status"]) if li else MasteryStatus.UNKNOWN

            def on_change(s: MasteryStatus) -> None:
                repo.set_mastery(item_type_map[kind], ref_id, s)

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
        rows = self.repo.db.conn.execute(
            "SELECT meaning, explanation, example, example_zh FROM phrase_occurrences "
            "WHERE phrase_id = ? ORDER BY id DESC", (pid,),
        ).fetchall()
        if not rows:
            self._browser.setPlainText("（已删除）")
            return
        main = self.repo.db.conn.execute(
            "SELECT text FROM phrases WHERE id = ?", (pid,)
        ).fetchone()
        lines = [f"<h2>{escape(main['text'])}</h2>"]
        seen: set[str] = set()
        for r in rows:
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
        rows = self.repo.db.conn.execute(
            "SELECT g.name, g.name_zh, o.source, o.explanation, o.why_used_here, "
            "o.simple_example, o.simple_example_zh, o.common_mistake "
            "FROM grammar_patterns g JOIN grammar_occurrences o ON o.grammar_id = g.id "
            "WHERE g.id = ? ORDER BY o.id DESC", (gid,),
        ).fetchall()
        if not rows:
            self._browser.setPlainText("（已删除）")
            return
        lines = [
            f"<h2>{escape(rows[0]['name_zh'] or rows[0]['name'])}</h2>",
            f"<p style='color:#888'>{escape(rows[0]['name'])}</p>",
        ]
        for r in rows[:3]:
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
            break
        self._browser.setHtml("".join(lines))

    def _render_expression(self, eid: int) -> None:
        r = self.repo.db.conn.execute(
            "SELECT text, meaning, usage, when_to_use, example, example_zh "
            "FROM academic_expressions WHERE id = ?", (eid,),
        ).fetchone()
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
        r = self.repo.db.conn.execute(
            "SELECT term, translation, simple_explanation, meaning_in_this_paper "
            "FROM concepts WHERE id = ?", (cid,),
        ).fetchone()
        if not r:
            self._browser.setPlainText("（已删除）")
            return
        title = r["term"] + (f"（{r['translation']}）" if r["translation"] else "")
        html = f"<h2>{escape(title)}</h2><p>{escape(r['simple_explanation'] or '')}</p>"
        if r["meaning_in_this_paper"]:
            html += f"<p><b>在本文中：</b>{escape(r['meaning_in_this_paper'])}</p>"
        self._browser.setHtml(html)

    def _render_pattern(self, pid: int) -> None:
        r = self.repo.db.conn.execute(
            "SELECT structure_summary, skeleton FROM sentence_patterns WHERE id = ?",
            (pid,),
        ).fetchone()
        if not r:
            self._browser.setPlainText("（已删除）")
            return
        html = f"<h2>{escape(r['structure_summary'])}</h2>"
        if r["skeleton"]:
            html += f"<p style='color:#888'>{escape(r['skeleton'])}</p>"
        self._browser.setHtml(html)
