"""历史记录页：搜索、筛选、收藏、恢复完整分析。"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from paperlingo.database.repository import Repository
from paperlingo.ui.widgets.common import EmptyState


class HistoryPage(QWidget):
    restore_requested = pyqtSignal(int)  # analysis_id
    reanalyze_requested = pyqtSignal(str)  # source_text

    PAGE = 30

    def __init__(self, repo: Repository, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.repo = repo
        self._search = ""
        self._paper_filter: int | None = None
        self._fav_only = False
        self._offset = 0
        self._setup_ui()

    def _setup_ui(self) -> None:
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(12)

        title = QLabel("历史记录")
        title.setProperty("role", "title")
        v.addWidget(title)

        filter_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索原文、论文、AI 结果……")
        self.search_edit.setProperty("role", "search")
        self.search_edit.textChanged.connect(self._on_search)
        filter_row.addWidget(self.search_edit, 2)

        self.paper_combo = QComboBox()
        self.paper_combo.addItem("全部论文", None)
        self.paper_combo.currentIndexChanged.connect(self._on_paper_filter)
        filter_row.addWidget(self.paper_combo, 1)

        self.fav_btn = QPushButton("★ 收藏")
        self.fav_btn.setProperty("role", "chip")
        self.fav_btn.setCheckable(True)
        self.fav_btn.toggled.connect(self._on_fav)
        filter_row.addWidget(self.fav_btn)
        v.addLayout(filter_row)

        self.list = QListWidget()
        self.list.setWordWrap(True)
        self.list.itemDoubleClicked.connect(self._open_item)
        v.addWidget(self.list, 1)

        btn_row = QHBoxLayout()
        self._load_more = QPushButton("加载更多")
        self._load_more.clicked.connect(self._more)
        self._open_btn = QPushButton("打开（恢复分析）")
        self._open_btn.setProperty("role", "primary")
        self._open_btn.clicked.connect(self._open_selected)
        self._fav_toggle = QPushButton("收藏 / 取消收藏")
        self._fav_toggle.clicked.connect(self._toggle_fav)
        self._reanalyze = QPushButton("用原文重新生成 Prompt")
        self._reanalyze.clicked.connect(self._reanalyze_selected)
        self._delete = QPushButton("删除")
        self._delete.clicked.connect(self._delete_selected)
        btn_row.addWidget(self._open_btn)
        btn_row.addWidget(self._fav_toggle)
        btn_row.addWidget(self._reanalyze)
        btn_row.addStretch(1)
        btn_row.addWidget(self._delete)
        btn_row.addWidget(self._load_more)
        v.addLayout(btn_row)

        self.empty = EmptyState("还没有分析记录", "去「阅读」页分析第一句论文吧")
        v.addWidget(self.empty)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self._offset = 0
        self.list.clear()
        self._reload_papers()
        self._load_page()
        has = self.list.count() > 0
        self.empty.setVisible(not has)
        self.list.setVisible(has)

    def _reload_papers(self) -> None:
        current = self._paper_filter
        self.paper_combo.blockSignals(True)
        self.paper_combo.clear()
        self.paper_combo.addItem("全部论文", None)
        for p in self.repo.list_papers_with_counts():
            title = p["title"] or "未命名论文"
            self.paper_combo.addItem(f"{title} ({p['cnt']})", p["id"])
        idx = self.paper_combo.findData(current)
        if idx >= 0:
            self.paper_combo.setCurrentIndex(idx)
        self.paper_combo.blockSignals(False)

    def _load_page(self) -> None:
        rows = self.repo.list_analyses(
            search=self._search, paper_id=self._paper_filter,
            favorites_only=self._fav_only, offset=self._offset, limit=self.PAGE,
        )
        for r in rows:
            preview = r.source_text.replace("\n", " ")
            if len(preview) > 90:
                preview = preview[:90] + "…"
            star = "★ " if r.is_favorite else ""
            paper = f"　{r.paper_title}" if r.paper_title else ""
            item = QListWidgetItem(f"{star}{preview}\n{r.created_at}{paper}　·　{r.analysis_depth}")
            item.setData(Qt.ItemDataRole.UserRole, r.id)
            self.list.addItem(item)
        self._offset += len(rows)
        self._load_more.setVisible(len(rows) == self.PAGE)

    def _more(self) -> None:
        self._load_page()

    def _on_search(self, text: str) -> None:
        self._search = text.strip()
        self.refresh()

    def _on_paper_filter(self, idx: int) -> None:
        self._paper_filter = self.paper_combo.itemData(idx)
        self.refresh()

    def _on_fav(self, checked: bool) -> None:
        self._fav_only = checked
        self.refresh()

    def _selected_id(self) -> int | None:
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _open_item(self, item: QListWidgetItem) -> None:
        self.restore_requested.emit(item.data(Qt.ItemDataRole.UserRole))

    def _open_selected(self) -> None:
        aid = self._selected_id()
        if aid:
            self.restore_requested.emit(aid)

    def _toggle_fav(self) -> None:
        aid = self._selected_id()
        if not aid:
            return
        data = self.repo.get_analysis(aid)
        if data:
            self.repo.set_favorite(aid, not bool(data["is_favorite"]))
            self.refresh()

    def _reanalyze_selected(self) -> None:
        aid = self._selected_id()
        if not aid:
            return
        data = self.repo.get_analysis(aid)
        if data:
            self.reanalyze_requested.emit(data["source_text"])

    def _delete_selected(self) -> None:
        aid = self._selected_id()
        if not aid:
            return
        answer = QMessageBox.question(
            self, "删除确认", "确定删除这条历史记录吗？对应知识点统计会保留。",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.repo.delete_analysis(aid)
            self.refresh()
