"""ListDetailPanel: compact item selector + detail panel.

Used by the vocabulary / grammar / expression / concept sections of the result
view and by the knowledge library. Clicking an item replaces the detail panel
content instead of rendering dozens of full cards.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from paperlingo.ui.widgets.common import _plain


class ListDetailPanel(QWidget):
    """Left: compact list of items (primary text + small sub text).
    Right: a detail widget supplied by the owner for the selected index."""

    selection_changed = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setHandleWidth(10)

        self._list = QListWidget()
        self._list.setWordWrap(True)
        self._list.currentRowChanged.connect(self._on_row)
        split.addWidget(self._list)

        self._detail = QWidget()
        self._detail_v = QVBoxLayout(self._detail)
        self._detail_v.setContentsMargins(12, 4, 4, 4)
        self._detail_v.setSpacing(10)
        self._empty_detail = QLabel("选择左侧条目查看详情")
        self._empty_detail.setProperty("role", "tertiary")
        self._empty_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._detail_v.addWidget(self._empty_detail)
        split.addWidget(self._detail)

        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([260, 480])

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(split)

    # ------------------------------------------------------------------
    def clear(self) -> None:
        self._list.clear()
        self._set_detail(None)

    def add_item(self, primary: str, sub: str = "", data: object = None) -> int:
        text = primary + (f"\n{sub}" if sub else "")
        item = QListWidgetItem(text)
        if data is not None:
            item.setData(Qt.ItemDataRole.UserRole, data)
        self._list.addItem(item)
        return self._list.count() - 1

    def select_row(self, row: int) -> None:
        self._list.setCurrentRow(row)

    def item_data(self, row: int) -> object | None:
        item = self._list.item(row)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def set_detail_widget(self, widget: QWidget | None) -> None:
        """Replace the detail panel content with `widget` (native widgets)."""
        self._set_detail(widget)

    def count(self) -> int:
        return self._list.count()

    # ------------------------------------------------------------------
    def _on_row(self, row: int) -> None:
        self.selection_changed.emit(row)

    def _set_detail(self, widget: QWidget | None) -> None:
        # Remove previous detail widgets
        while self._detail_v.count():
            item = self._detail_v.takeAt(0)
            w = item.widget()
            if w is self._empty_detail:
                continue
            if w:
                w.setParent(None)
                w.deleteLater()
        if widget is None:
            self._empty_detail.show()
            self._detail_v.addWidget(self._empty_detail)
        else:
            self._empty_detail.hide()
            self._detail_v.addWidget(widget)


def detail_label(text: str, role: str = "") -> QLabel:
    """Plain-text wrapped label for detail content (AI data is untrusted)."""
    lbl = _plain(QLabel(text))
    lbl.setWordWrap(True)
    lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    if role:
        lbl.setProperty("role", role)
    return lbl


def detail_inset(lines: list[str], role: str = "") -> QWidget:
    """A small inset box with wrapped plain-text lines (e.g. an example)."""
    from PyQt6.QtWidgets import QFrame

    box = QFrame()
    box.setProperty("role", "inset")
    v = QVBoxLayout(box)
    v.setContentsMargins(12, 8, 12, 8)
    v.setSpacing(4)
    for line in lines:
        lbl = detail_label(line, role)
        v.addWidget(lbl)
    return box
