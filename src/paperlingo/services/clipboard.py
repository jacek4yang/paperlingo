"""剪贴板服务（UI 无关封装，便于测试与复用）。"""

from __future__ import annotations


class ClipboardError(RuntimeError):
    pass


def read_text() -> str:
    """读取系统剪贴板文本（依赖 Qt，须在 QApplication 创建后调用）。"""
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
