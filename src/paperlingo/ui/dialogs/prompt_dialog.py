"""Dialog for viewing the prompt or the raw AI response."""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout

from paperlingo.prompt.compiler import CompiledPrompt
from paperlingo.ui.widgets.common import CopyButton


class PromptDialog(QDialog):
    def __init__(self, prompt: CompiledPrompt, parent=None, title: str = "Prompt") -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(720, 640)
        v = QVBoxLayout(self)
        v.setSpacing(10)

        meta = QLabel(f"模板 {prompt.template_id} · 版本 {prompt.template_version}")
        meta.setProperty("role", "tertiary")
        v.addWidget(meta)

        edit = QPlainTextEdit()
        edit.setPlainText(prompt.text)
        edit.setReadOnly(True)
        v.addWidget(edit, 1)

        row = QHBoxLayout()
        row.addStretch(1)
        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        row.addWidget(CopyButton(lambda: prompt.text))
        row.addWidget(close)
        v.addLayout(row)
