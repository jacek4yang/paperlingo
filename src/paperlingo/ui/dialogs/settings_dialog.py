"""Settings dialog: theme / font / default depth / default profile / export."""

from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from paperlingo.database.repository import Repository
from paperlingo.domain.analysis import DEPTH_LABELS
from paperlingo.prompt.profiles import list_profiles
from paperlingo.services.settings import THEME_LABELS, AppSettings


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, repo: Repository, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(460)
        self._settings = settings
        self.repo = repo

        v = QVBoxLayout(self)
        v.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(12)

        self.theme_combo = QComboBox()
        for key, label in THEME_LABELS.items():
            self.theme_combo.addItem(label, key)
        idx = self.theme_combo.findData(settings.theme)
        self.theme_combo.setCurrentIndex(max(0, idx))
        form.addRow("主题", self.theme_combo)

        font_row = QHBoxLayout()
        self.font_slider = QSlider()
        self.font_slider.setRange(80, 140)
        self.font_slider.setValue(int(settings.font_scale * 100))
        self.font_slider.setTickPosition(QSlider.TickPosition.NoTicks)
        self.font_label = QLabel(f"{settings.font_scale:.2f}×")
        self.font_slider.valueChanged.connect(lambda val: self.font_label.setText(f"{val / 100:.2f}×"))
        font_row.addWidget(self.font_slider, 1)
        font_row.addWidget(self.font_label)
        form.addRow("字体大小", font_row)

        self.depth_combo = QComboBox()
        for key, label in DEPTH_LABELS.items():
            self.depth_combo.addItem(label, key)
        idx = self.depth_combo.findData(settings.default_depth)
        self.depth_combo.setCurrentIndex(max(0, idx))
        form.addRow("默认分析深度", self.depth_combo)

        self.profile_combo = QComboBox()
        for p in list_profiles():
            self.profile_combo.addItem(p.display_name, p.profile_id)
        idx = self.profile_combo.findData(settings.default_profile)
        self.profile_combo.setCurrentIndex(max(0, idx))
        form.addRow("默认 Web AI", self.profile_combo)

        v.addLayout(form)

        # Data
        db_label = QLabel(f"数据库位置：{repo.db.path}")
        db_label.setWordWrap(True)
        db_label.setProperty("role", "tertiary")
        v.addWidget(db_label)

        export_row = QHBoxLayout()
        btn_json = QPushButton("导出知识库 (JSON)")
        btn_json.clicked.connect(self._export_json)
        btn_csv = QPushButton("导出单词 (CSV)")
        btn_csv.clicked.connect(self._export_csv)
        export_row.addWidget(btn_json)
        export_row.addWidget(btn_csv)
        export_row.addStretch(1)
        v.addLayout(export_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        v.addWidget(buttons)

    # ------------------------------------------------------------------
    def result_settings(self) -> AppSettings:
        s = self._settings
        s.theme = self.theme_combo.currentData() or "system"
        s.font_scale = self.font_slider.value() / 100
        s.default_depth = self.depth_combo.currentData() or "standard"
        s.default_profile = self.profile_combo.currentData() or "generic"
        return s

    # ------------------------------------------------------------------
    def _export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "导出知识库", "paperlingo_export.json", "JSON (*.json)"
        )
        if not path:
            return
        try:
            data = self.repo.export_json()
            Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as e:
            QMessageBox.critical(self, "导出失败", f"写入文件失败：\n{e}")
            return
        QMessageBox.information(self, "导出完成", f"已导出到\n{path}")

    def _export_csv(self) -> None:
        import csv

        path, _ = QFileDialog.getSaveFileName(
            self, "导出单词", "paperlingo_words.csv", "CSV (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["单词", "词性", "出现次数", "语境含义", "来源论文"])
                for r in self.repo.list_words(limit=100000):
                    writer.writerow([
                        r.lemma, r.pos, r.occurrences,
                        "；".join(r.meanings), "；".join(r.papers),
                    ])
        except OSError as e:
            QMessageBox.critical(self, "导出失败", f"写入文件失败：\n{e}")
            return
        QMessageBox.information(self, "导出完成", f"已导出到\n{path}")
