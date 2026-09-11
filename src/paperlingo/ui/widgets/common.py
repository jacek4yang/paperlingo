"""通用小组件：卡片、按钮、空状态、错误状态、骨架屏等。"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from paperlingo.domain.learning import MasteryStatus
from paperlingo.services.clipboard import write_text


class Card(QFrame):
    """Base card container: rounded card with subtle border, title + content."""

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "card")
        self._v = QVBoxLayout(self)
        self._v.setContentsMargins(18, 14, 18, 14)
        self._v.setSpacing(10)
        self._title_label: QLabel | None = None
        if title:
            self.set_title(title)

    def set_title(self, title: str) -> None:
        if self._title_label is None:
            self._title_label = QLabel()
            self._title_label.setProperty("role", "h2")
            self._v.addWidget(self._title_label)
        self._title_label.setText(title)

    def body(self) -> QVBoxLayout:
        return self._v


def _plain(lbl: QLabel) -> QLabel:
    """Force plain-text rendering on a QLabel.

    QLabel auto-detects rich text by default: AI content containing
    <img>/<b>/<style> tags would be interpreted. Every label displaying
    AI/user data must go through here.
    """
    lbl.setTextFormat(Qt.TextFormat.PlainText)
    return lbl


def _flow_text_label(text: str, role: str = "") -> QLabel:
    lbl = _plain(QLabel(text))
    lbl.setWordWrap(True)
    lbl.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse
    )
    if role:
        lbl.setProperty("role", role)
    return lbl











class CollapsibleCard(Card):
    """Collapsible card: title bar + toggle; secondary content starts collapsed."""

    def __init__(self, title: str, expanded: bool = False,
                 parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self._expanded = expanded
        self._content = QWidget()
        self._content_v = QVBoxLayout(self._content)
        self._content_v.setContentsMargins(0, 0, 0, 0)
        self._content_v.setSpacing(10)
        self._v.addWidget(self._content)

        header = QHBoxLayout()
        self._toggle = QPushButton("收起" if expanded else "展开")
        self._toggle.setProperty("role", "ghost")
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.clicked.connect(self.toggle)
        header.addStretch(1)
        header.addWidget(self._toggle)
        self._v.addLayout(header)
        self._content.setVisible(expanded)

    def toggle(self) -> None:
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        self._toggle.setText("收起" if self._expanded else "展开")

    def add_content(self, w: QWidget) -> None:
        self._content_v.addWidget(w)

    def add_content_layout(self, lay: QVBoxLayout | QHBoxLayout) -> None:
        self._content_v.addLayout(lay)


class CopyButton(QPushButton):
    """Copy text on click and briefly show the copied state."""

    def __init__(self, get_text: Callable[[], str], label: str = "复制",
                 parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self._get_text = get_text
        self._orig = label
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(1600)
        self._timer.timeout.connect(self._reset)
        self.clicked.connect(self._copy)

    def _copy(self) -> None:
        try:
            write_text(self._get_text())
        except Exception:
            return
        self.setText("已复制")
        self.setEnabled(False)
        self._timer.start()

    def _reset(self) -> None:
        self.setText(self._orig)
        self.setEnabled(True)


class EmptyState(QWidget):
    """Empty state: minimal text-only (title + subtitle + optional action button)."""

    def __init__(self, title: str, subtitle: str = "",
                 action_text: str = "", on_action: Callable[[], None] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.setSpacing(10)
        t = QLabel(title)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setProperty("role", "title")
        v.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setAlignment(Qt.AlignmentFlag.AlignCenter)
            s.setProperty("role", "secondary")
            s.setWordWrap(True)
            v.addWidget(s)
        if action_text and on_action:
            btn = QPushButton(action_text)
            btn.setProperty("role", "primary")
            btn.clicked.connect(on_action)
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(btn)
            row.addStretch(1)
            v.addLayout(row)


class ErrorState(QWidget):
    """Error state: title + detail + optional action buttons."""

    def __init__(self, title: str, detail: str = "",
                 buttons: list[tuple[str, Callable[[], None]]] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.setSpacing(10)
        t = QLabel(title)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setProperty("role", "title")
        v.addWidget(t)
        if detail:
            d = _plain(QLabel(detail))
            d.setAlignment(Qt.AlignmentFlag.AlignCenter)
            d.setProperty("role", "secondary")
            d.setWordWrap(True)
            d.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            v.addWidget(d)
        if buttons:
            row = QHBoxLayout()
            row.addStretch(1)
            for text, cb in buttons:
                b = QPushButton(text)
                b.clicked.connect(cb)
                row.addWidget(b)
            row.addStretch(1)
            v.addLayout(row)


class SkeletonLoading(QWidget):
    """Simple skeleton: a few grey placeholder bars."""

    def __init__(self, lines: int = 4, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setSpacing(12)
        v.setContentsMargins(4, 4, 4, 4)
        for i in range(lines):
            bar = QLabel()
            bar.setProperty("role", "skeleton")
            bar.setFixedHeight(16 if i else 26)
            w = [100, 85, 92, 70, 88][i % 5]
            bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            bar.setMaximumWidth(int(w * 6))
            v.addWidget(bar)
        v.addStretch(1)


class LearningStatusButtons(QWidget):
    """Three-state mastery button group (known / unfamiliar / hard)."""

    def __init__(self, current: MasteryStatus,
                 on_change: Callable[[MasteryStatus], None],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self._buttons: dict[MasteryStatus, QPushButton] = {}
        self._current = current
        self._on_change = on_change
        opts = [
            (MasteryStatus.KNOWN, "认识"),
            (MasteryStatus.UNFAMILIAR, "不熟"),
            (MasteryStatus.HARD, "不会"),
        ]
        for status, label in opts:
            b = QPushButton(label)
            b.setProperty("role", "chip")
            b.setCheckable(True)
            b.setChecked(status == current)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, s=status: self._pick(s))
            lay.addWidget(b)
            self._buttons[status] = b
        self._refresh()

    def _pick(self, status: MasteryStatus) -> None:
        self._current = status
        self._refresh()
        self._on_change(status)

    def _refresh(self) -> None:
        for s, b in self._buttons.items():
            b.setChecked(s == self._current)
