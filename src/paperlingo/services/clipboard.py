"""Clipboard service (UI-independent wrapper, easy to test and reuse)."""

from __future__ import annotations


class ClipboardError(RuntimeError):
    pass


def read_text() -> str:
    """Read system clipboard text (Qt-dependent; requires a QApplication)."""
    from PyQt6.QtWidgets import QApplication

    cb = QApplication.clipboard()
    if cb is None:
        raise ClipboardError("剪贴板不可用")
    text = cb.text()
    return text or ""


def write_text(text: str) -> None:
    from PyQt6.QtWidgets import QApplication

    cb = QApplication.clipboard()
    if cb is None:
        raise ClipboardError("剪贴板不可用")
    cb.setText(text)
