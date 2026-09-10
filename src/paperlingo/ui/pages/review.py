"""复习页：到期学习项的问答式复习，Again/Hard/Good/Easy 四档评分。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from paperlingo.database.repository import Repository
from paperlingo.domain.learning import ITEM_TYPE_LABELS, RATING_LABELS, ItemType, Rating
from paperlingo.learning.review import review_item
from paperlingo.ui.widgets.common import EmptyState, _plain

_TYPE_ORDER = {ItemType.WORD.value: 0, ItemType.PHRASE.value: 1, ItemType.GRAMMAR.value: 2,
               ItemType.EXPRESSION.value: 3, ItemType.CONCEPT.value: 4}


class ReviewPage(QWidget):
    def __init__(self, repo: Repository, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.repo = repo
        self._queue: list = []
        self._pos = 0
        self._revealed = False
        self._session_done = 0
        self._setup_ui()

    def _setup_ui(self) -> None:
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(12)

        title = QLabel("复习")
        title.setProperty("role", "title")
        v.addWidget(title)

        self._progress = QProgressBar()
        self._progress.setFixedHeight(8)
        self._progress.setTextVisible(False)
        v.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setProperty("role", "secondary")
        v.addWidget(self._status)

        self._empty = EmptyState(
            "今天没有到期的复习",
            "在知识库或阅读页把知识点标记为「不熟 / 不会」，它们会进入学习队列。",
        )
        v.addWidget(self._empty, 1)

        # 复习卡片区
        self._card_area = QScrollArea()
        self._card_area.setWidgetResizable(True)
        self._card_area.setFrameShape(QScrollArea.Shape.NoFrame)
        card_inner = QWidget()
        self._card_v = QVBoxLayout(card_inner)
        self._card_v.setContentsMargins(8, 8, 8, 8)
        self._card_v.setSpacing(14)
        self._card_v.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._card_area.setWidget(card_inner)
        v.addWidget(self._card_area, 1)

        # 类型标签 + 正面（内容来自数据库/AI，强制纯文本渲染）
        self._type_label = _plain(QLabel())
        self._type_label.setProperty("role", "tertiary")
        self._card_v.addWidget(self._type_label)

        self._front = _plain(QLabel())
        self._front.setWordWrap(True)
        self._front.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._front.setStyleSheet("font-size: 22px; font-weight: 600;")
        self._card_v.addWidget(self._front)

        self._back = _plain(QLabel())
        self._back.setWordWrap(True)
        self._back.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._back.setStyleSheet("font-size: 15px;")
        self._back.hide()
        self._card_v.addWidget(self._back)

        btn_row = QHBoxLayout()
        self._show_btn = QPushButton("显示答案")
        self._show_btn.setProperty("role", "primary")
        self._show_btn.clicked.connect(self._reveal)
        btn_row.addWidget(self._show_btn)
        self._card_v.addLayout(btn_row)

        self._rate_row = QHBoxLayout()
        self._rate_buttons: list[QPushButton] = []
        for r in Rating:
            b = QPushButton(RATING_LABELS[r])
            b.clicked.connect(lambda _=False, rr=r: self._rate(rr))
            self._rate_row.addWidget(b)
            self._rate_buttons.append(b)
        self._rate_row.addStretch(1)
        self._card_v.addLayout(self._rate_row)

        self._card_area.hide()
        self._refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        due = self.repo.due_items(limit=50)
        due.sort(key=lambda it: (_TYPE_ORDER.get(it.item_type, 9), it.item_id))
        self._queue = due
        self._pos = 0
        self._session_done = 0
        self._progress.setMaximum(max(1, len(due)))
        self._progress.setValue(0)
        self._show_current()

    def _show_current(self) -> None:
        has = self._pos < len(self._queue)
        self._empty.setVisible(not has)
        self._card_area.setVisible(has)
        self._status.setVisible(has)
        if not has:
            if self._session_done:
                self._status.show()
                self._status.setText(f"本轮完成，共复习 {self._session_done} 项")
            else:
                self._status.hide()
            return
        item = self._queue[self._pos]
        type_zh = ITEM_TYPE_LABELS.get(ItemType(item.item_type), item.item_type)
        self._type_label.setText(f"{type_zh} · 第 {self._pos + 1} / {len(self._queue)} 项")
        self._front.setText(item.front)
        self._back.setText(item.back)
        self._back.hide()
        self._show_btn.show()
        for b in self._rate_buttons:
            b.hide()
        self._progress.setValue(self._pos)
        self._status.setText("想一想它的含义，再点「显示答案」")

    def _reveal(self) -> None:
        self._revealed = True
        self._back.show()
        self._show_btn.hide()
        for b in self._rate_buttons:
            b.show()
        self._status.setText("回忆得怎么样？")

    def _rate(self, rating: Rating) -> None:
        if self._pos >= len(self._queue):
            return
        item = self._queue[self._pos]
        ok = review_item(self.repo, item.item_id, rating)
        if ok:
            self._session_done += 1
        self._pos += 1
        self._show_current()
