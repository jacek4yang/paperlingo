"""阅读页：左输入（原文/上下文/论文信息/深度 + Prompt 生成/复制 + Response 粘贴解析），右结果。"""

from __future__ import annotations

from contextlib import suppress

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
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
from paperlingo.ui.theme import Palette
from paperlingo.ui.widgets.common import (
    CopyButton,
    EmptyState,
    ErrorState,
    SkeletonLoading,
)
from paperlingo.ui.widgets.result_view import ResultView

DEPTHS = list(DEPTH_LABELS.keys())


class ReadingPage(QWidget):
    #: 一次成功解析并保存后发出 analysis_id
    analysis_saved = pyqtSignal(int)

    def __init__(self, repo: Repository, palette: Palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.repo = repo
        self._palette = palette
        self._prompt: CompiledPrompt | None = None
        self._compiler = PromptCompiler()

        self._draft = DraftStore(repo)
        self._setup_ui()
        self._apply_defaults()
        self._load_draft()

    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(12)
        root.addWidget(self._splitter)

        # ---------------- 左：输入 ----------------
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        left_scroll.setMinimumWidth(380)
        left_scroll.setMaximumWidth(560)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(20, 20, 8, 20)
        lv.setSpacing(12)

        title = QLabel("阅读")
        title.setProperty("role", "title")
        lv.addWidget(title)

        lv.addWidget(QLabel("原文"))
        self.source_edit = QPlainTextEdit()
        self.source_edit.setPlaceholderText(
            "Paste the sentence or paragraph here...\n\n"
            "把论文中没看懂的英文放到这里。我们不只翻译它，还会把它拆开讲明白。"
        )
        self.source_edit.setMinimumHeight(140)
        lv.addWidget(self.source_edit)

        counter_row = QHBoxLayout()
        self._counter = QLabel("0 词")
        self._counter.setProperty("role", "tertiary")
        counter_row.addStretch(1)
        counter_row.addWidget(self._counter)
        lv.addLayout(counter_row)
        self.source_edit.textChanged.connect(self._update_counter)

        self._prev_edit = QPlainTextEdit()
        self._prev_edit.setPlaceholderText("Previous context (optional) — 上文，可选")
        self._prev_edit.setFixedHeight(64)
        self._next_edit = QPlainTextEdit()
        self._next_edit.setPlaceholderText("Following context (optional) — 下文，可选")
        self._next_edit.setFixedHeight(64)
        prev_row = QLabel("上文 / 下文（可选）")
        prev_row.setProperty("role", "secondary")
        lv.addWidget(prev_row)
        lv.addWidget(self._prev_edit)
        lv.addWidget(self._next_edit)

        # 论文信息
        info_head = QLabel("论文信息（可选）")
        info_head.setProperty("role", "secondary")
        lv.addWidget(info_head)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Paper title 论文标题")
        self.doi_edit = QLineEdit()
        self.doi_edit.setPlaceholderText("DOI / URL")
        self.authors_edit = QLineEdit()
        self.authors_edit.setPlaceholderText("Authors 作者")
        self.domain_combo = QComboBox()
        for value, label in DOMAIN_OPTIONS:
            # Stable English value goes into the prompt; the label is UI-only.
            self.domain_combo.addItem(label, value)
        grid.addWidget(self.title_edit, 0, 0)
        grid.addWidget(self.doi_edit, 0, 1)
        grid.addWidget(self.authors_edit, 1, 0)
        grid.addWidget(self.domain_combo, 1, 1)
        lv.addLayout(grid)

        depth_row = QHBoxLayout()
        depth_row.setSpacing(8)
        self.depth_combo = QComboBox()
        for d in DEPTHS:
            self.depth_combo.addItem(DEPTH_LABELS[d], d)
        self.profile_combo = QComboBox()
        for prof in list_profiles():
            self.profile_combo.addItem(prof.display_name, prof.profile_id)
        depth_row.addWidget(self.depth_combo, 1)
        depth_row.addWidget(self.profile_combo, 1)
        lv.addLayout(depth_row)

        # Prompt 操作
        prompt_row = QHBoxLayout()
        prompt_row.setSpacing(8)
        self._gen_btn = QPushButton("生成 Prompt")
        self._gen_btn.setProperty("role", "primary")
        self._gen_btn.clicked.connect(self._generate_prompt)
        self._view_btn = QPushButton("查看")
        self._view_btn.setEnabled(False)
        self._view_btn.clicked.connect(self._show_prompt_dialog)
        self._copy_btn = CopyButton(lambda: self._prompt.text if self._prompt else "")
        self._copy_btn.setEnabled(False)
        prompt_row.addWidget(self._gen_btn, 1)
        prompt_row.addWidget(self._view_btn)
        prompt_row.addWidget(self._copy_btn)
        lv.addLayout(prompt_row)

        self._prompt_preview = QPlainTextEdit()
        self._prompt_preview.setReadOnly(True)
        self._prompt_preview.setVisible(False)
        self._prompt_preview.setFixedHeight(120)
        self._prompt_preview.setPlaceholderText("Prompt 预览……")
        lv.addWidget(self._prompt_preview)

        # 分割线
        line = QFrame()
        line.setProperty("role", "hline")
        lv.addWidget(line)

        # Response
        resp_head = QLabel("粘贴 AI 结果")
        resp_head.setProperty("role", "secondary")
        lv.addWidget(resp_head)
        self.response_edit = QPlainTextEdit()
        self.response_edit.setPlaceholderText(
            "把 Web AI 返回的完整内容粘贴到这里（支持 JSON 前后带说明文字）"
        )
        self.response_edit.setMinimumHeight(120)
        lv.addWidget(self.response_edit)

        resp_row = QHBoxLayout()
        resp_row.setSpacing(8)
        self._from_clip_btn = QPushButton("从剪贴板读取")
        self._from_clip_btn.clicked.connect(self._paste_from_clipboard)
        self._parse_btn = QPushButton("解析")
        self._parse_btn.setProperty("role", "primary")
        self._parse_btn.clicked.connect(self._parse_response)
        resp_row.addWidget(self._from_clip_btn)
        resp_row.addWidget(self._parse_btn, 1)
        lv.addLayout(resp_row)

        self._error_area = QVBoxLayout()
        lv.addLayout(self._error_area)

        # 示例
        self._example_btn = QPushButton("加载示例")
        self._example_btn.setProperty("role", "ghost")
        self._example_btn.clicked.connect(self._load_example)
        lv.addWidget(self._example_btn)
        lv.addStretch(1)

        left_scroll.setWidget(left)
        self._splitter.addWidget(left_scroll)

        # ---------------- 右：结果 ----------------
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(8, 20, 20, 20)
        rv.setSpacing(12)
        self.result_view = ResultView(self._palette)
        self.result_view.on_learn = self._add_learning_item
        rv.addWidget(self.result_view)
        self._empty = EmptyState(
            "把论文中没看懂的英文放到这里",
            "我们不只翻译它，还会把它拆开讲明白。\n左侧粘贴英文 → 生成 Prompt → 粘贴回 AI 结果。",
            "粘贴英文",
            lambda: self.source_edit.setFocus(),
        )
        rv.addWidget(self._empty)
        self._loading = SkeletonLoading()
        self._loading.hide()
        self._empty.show()
        self.result_view.hide()
        rv.addWidget(self._loading)
        right.setLayout(rv)
        self._splitter.addWidget(right)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([460, 900])

        # 快捷键
        QShortcut(QKeySequence("Ctrl+Return"), self, self._generate_prompt)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, self._copy_prompt_action)

        # 草稿自动保存定时器
        self._draft_timer = QTimer(self)
        self._draft_timer.setInterval(3000)
        self._draft_timer.timeout.connect(self._save_draft)
        self._draft_timer.start()
        self.source_edit.textChanged.connect(self._save_draft)
        self._prev_edit.textChanged.connect(self._save_draft)
        self._next_edit.textChanged.connect(self._save_draft)

    def _apply_defaults(self) -> None:
        from paperlingo.services.settings import AppSettings

        s = AppSettings.load(self.repo)
        idx = self.depth_combo.findData(s.default_depth)
        if idx >= 0:
            self.depth_combo.setCurrentIndex(idx)
        idx = self.profile_combo.findData(s.default_profile)
        if idx >= 0:
            self.profile_combo.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    def _update_counter(self) -> None:
        text = self.source_edit.toPlainText()
        words = len([w for w in text.split() if w.strip()])
        self._counter.setText(f"{words} 词 · {len(text)} 字符")

    # ------------------------------------------------------------------
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
        try:
            req = self._collect_request()
            self._prompt = self._compiler.compile(req, self.profile_combo.currentData() or "generic")
        except Exception as e:
            self._show_error("生成 Prompt 失败", str(e))
            return
        self._view_btn.setEnabled(True)
        self._copy_btn.setEnabled(True)
        self._prompt_preview.setVisible(True)
        self._prompt_preview.setPlainText(self._prompt.text)
        self._copy_btn._copy()  # 生成后直接复制，减少一步操作

    def _copy_prompt_action(self) -> None:
        if self._prompt:
            self._copy_btn._copy()

    def _show_prompt_dialog(self) -> None:
        from paperlingo.ui.dialogs.prompt_dialog import PromptDialog

        if self._prompt:
            dlg = PromptDialog(self._prompt, self)
            dlg.exec()

    # ------------------------------------------------------------------
    def _paste_from_clipboard(self) -> None:
        # 剪贴板被占用时读取失败属于常见情形，静默即可
        with suppress(ClipboardError):
            self.response_edit.setPlainText(read_text())

    def _parse_response(self) -> None:
        raw = self.response_edit.toPlainText()
        self._clear_error()
        self._loading.show()
        self.result_view.hide()
        self._empty.hide()
        # 用 QTimer 延迟一帧执行解析，让骨架屏先显示
        QTimer.singleShot(60, lambda: self._do_parse(raw))

    def _do_parse(self, raw: str) -> None:
        self._loading.hide()
        result = parse_response(raw)
        if not result.ok or result.data is None:
            self.result_view.hide()
            self._empty.hide()
            err = result.error
            self._show_error(
                "无法解析 AI 返回结果",
                (err.describe() if err else "未知错误"),
                repair=True,
                raw=raw,
            )
            return
        # Pydantic 校验
        try:
            analysis = PaperAnalysis.model_validate(result.data)
        except Exception as e:
            self._show_error("AI 返回内容未通过校验", str(e)[:400], repair=True, raw=raw)
            return
        # 保存
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
        self._draft.clear()
        self._last_analysis_id = analysis_id
        self.analysis_saved.emit(analysis_id)

    def _show_analysis(self, analysis: PaperAnalysis) -> None:
        # 单词颜色映射：把 words 的 surface 映射到角色色
        word_map: dict[str, tuple[str, str]] = {}
        for w in analysis.words:
            if not w.surface:
                continue
            info = f"{w.pos_zh or ''}\n本句：{w.meaning_in_context}"
            if w.lemma and w.lemma != w.surface:
                info += f"\n原形：{w.lemma}"
            word_map[w.surface] = ("role_misc", info)
        self.result_view.show_analysis(analysis, word_map)
        self.result_view.show()
        self._empty.hide()

    def _show_error(self, title: str, detail: str, *, repair: bool = False, raw: str = "") -> None:
        self._clear_error()
        buttons: list[tuple[str, object]] = []
        if repair and raw:
            def copy_repair() -> None:
                write_text(compile_repair_prompt("JSON 解析失败", raw))
            def view_raw() -> None:
                from paperlingo.prompt.compiler import CompiledPrompt
                from paperlingo.ui.dialogs.prompt_dialog import PromptDialog

                cp = CompiledPrompt(text=raw, template_id="raw", template_version="raw", profile_id="")
                PromptDialog(cp, self, title="原始 AI Response").exec()
            buttons.append(("复制修复 Prompt", copy_repair))
            buttons.append(("查看原始 Response", view_raw))
        err = ErrorState(title, detail, buttons)  # type: ignore[arg-type]
        self._error_area.addWidget(err)

    def _clear_error(self) -> None:
        while self._error_area.count():
            item = self._error_area.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ------------------------------------------------------------------
    def _add_learning_item(self, item_type: str, key: str, state: str) -> None:
        from paperlingo.domain.learning import MasteryStatus

        ref_id = self.repo.find_knowledge_item_id(item_type, key)
        if ref_id is not None:
            self.repo.set_mastery(item_type, ref_id, MasteryStatus(state))

    # ------------------------------------------------------------------
    def _load_example(self) -> None:
        self.source_edit.setPlainText(
            "In this survey, we address this gap through a curated corpus of 247 papers "
            "and a lifecycle-based, systems-oriented analytical framework."
        )

    # ------------------------------------------------------------------
    def _save_draft(self) -> None:
        # DraftStore.save 内部已静默处理 IO 失败（草稿丢失可接受）
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
        if data.get("response_text"):
            self.response_edit.setPlainText(data["response_text"])

    # ------------------------------------------------------------------
    def restore_analysis(self, analysis_id: int, analysis: PaperAnalysis, meta: dict) -> None:
        """历史记录恢复：填入原文与信息，展示结果。"""
        self.source_edit.setPlainText(analysis.source_text)
        self._prev_edit.setPlainText(meta.get("previous_context", ""))
        self._next_edit.setPlainText(meta.get("following_context", ""))
        self.title_edit.setText(meta.get("paper_title", ""))
        self.doi_edit.setText(meta.get("paper_doi", ""))
        self.authors_edit.setText(meta.get("paper_authors", ""))
        self._show_analysis(analysis)
