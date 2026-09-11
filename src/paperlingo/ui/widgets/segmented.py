"""SegmentedControl: a restrained chip-style section switcher.

Used for the result-view section navigation (概览 / 结构 / 语法 / 词汇 / 表达 /
概念). One selected segment shows through subtle background/accent treatment;
no emoji, no gradients.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QWidget


class SegmentedControl(QWidget):
    """A horizontal row of checkable chips. Emits `selected(key)` on change."""

    selected = pyqtSignal(str)

    def __init__(self, options: list[tuple[str, str]], parent: QWidget | None = None) -> None:
        """options: list of (stable key, display label) pairs."""
        super().__init__(parent)
        self._keys: list[str] = []
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for i, (key, label) in enumerate(options):
            b = QPushButton(label)
            b.setProperty("role", "chip")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            self._group.addButton(b, i)
            lay.addWidget(b)
            self._keys.append(key)
            b.clicked.connect(lambda _=False, k=key: self.selected.emit(k))
        lay.addStretch(1)
        if options:
            self._group.button(0).setChecked(True)

    def select_key(self, key: str) -> None:
        """Programmatically select a segment without emitting `selected`."""
        if key in self._keys:
            idx = self._keys.index(key)
            self._group.button(idx).setChecked(True)

    def current_key(self) -> str | None:
        checked = self._group.checkedId()
        return self._keys[checked] if checked >= 0 else None
