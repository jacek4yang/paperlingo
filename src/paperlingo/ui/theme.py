"""Theme system: Light / Dark QSS sets, optionally following the system.

Design goal: restrained and modern (somewhere between Windows 11 / Linear /
Notion) — large whitespace, few borders, 8-12px radii, clear hierarchy, no
harsh gradients.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

THEME_LIGHT = "light"
THEME_DARK = "dark"


def system_theme() -> str:
    """Detect the Windows system theme (registry AppsUseLightTheme)."""
    if sys.platform != "win32":
        return THEME_LIGHT
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return THEME_LIGHT if value else THEME_DARK
    except OSError:
        return THEME_LIGHT


# ---------------------------------------------------------------------------
# Palette


@dataclass
class Palette:
    """Theme palette (not frozen: MainWindow updates the shared instance in place on switch)."""

    name: str

    # Base surfaces
    bg: str          # window background
    bg_card: str     # card background
    bg_input: str    # input background
    bg_hover: str    # hover background
    bg_selected: str  # selected background
    border: str      # border
    divider: str     # divider

    # Text
    text: str        # primary text
    text_secondary: str
    text_tertiary: str
    text_disabled: str
    text_on_accent: str

    # Accent (restrained blue)
    accent: str
    accent_hover: str
    accent_soft: str  # 主色浅底

    # Semantic colors (low saturation)
    success: str
    warning: str
    danger: str
    success_soft: str
    warning_soft: str
    danger_soft: str

    # Grammar-role colors (restrained semantic highlighting)
    role_subject: str
    role_predicate: str
    role_object: str
    role_modifier: str
    role_clause: str
    role_misc: str


LIGHT = Palette(
    name="light",
    bg="#f7f7f9",
    bg_card="#ffffff",
    bg_input="#ffffff",
    bg_hover="#f1f2f4",
    bg_selected="#eef3ff",
    border="#e4e5e9",
    divider="#ececef",
    text="#1f2328",
    text_secondary="#59626d",
    text_tertiary="#8a919c",
    text_disabled="#b9bec6",
    text_on_accent="#ffffff",
    accent="#3b6ef5",
    accent_hover="#2f5fe0",
    accent_soft="#eef3ff",
    success="#2f9e63",
    warning="#c47f17",
    danger="#d64545",
    success_soft="#e9f6ef",
    warning_soft="#faf3e3",
    danger_soft="#fdeeee",
    role_subject="#3b6ef5",
    role_predicate="#2f9e63",
    role_object="#c47f17",
    role_modifier="#8f6ad6",
    role_clause="#d166a4",
    role_misc="#5a8fbf",
)

DARK = Palette(
    name="dark",
    bg="#1b1d21",
    bg_card="#24262b",
    bg_input="#24262b",
    bg_hover="#2c2f35",
    bg_selected="#2b3550",
    border="#34373d",
    divider="#2e3137",
    text="#e6e8ea",
    text_secondary="#a3aab4",
    text_tertiary="#6f7680",
    text_disabled="#565b63",
    text_on_accent="#ffffff",
    accent="#6d92f7",
    accent_hover="#82a2f8",
    accent_soft="#26304a",
    success="#5cb87e",
    warning="#d9a04a",
    danger="#e07070",
    success_soft="#253528",
    warning_soft="#37301f",
    danger_soft="#3a2626",
    role_subject="#7c9bf8",
    role_predicate="#6fc492",
    role_object="#dcae63",
    role_modifier="#b39ae8",
    role_clause="#e28bc0",
    role_misc="#7fb0d8",
)

PALETTES = {THEME_LIGHT: LIGHT, THEME_DARK: DARK}


def palette(theme: str) -> Palette:
    return PALETTES.get(theme, LIGHT)


# ---------------------------------------------------------------------------


def build_qss(p: Palette) -> str:
    """Build the full QSS. Every color comes from the Palette; no raw values."""
    return f"""
* {{
    outline: none;
}}
QWidget {{
    background: {p.bg};
    color: {p.text};
    font-family: "Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI", "微软雅黑", sans-serif;
    font-size: 13px;
}}
QMainWindow, QDialog {{
    background: {p.bg};
}}

/* ---------- 文本 ---------- */
QLabel {{
    background: transparent;
}}
QLabel[role="title"] {{
    font-size: 17px;
    font-weight: 600;
}}
QLabel[role="h2"] {{
    font-size: 14px;
    font-weight: 600;
}}
QLabel[role="secondary"] {{
    color: {p.text_secondary};
}}
QLabel[role="tertiary"] {{
    color: {p.text_tertiary};
    font-size: 12px;
}}

/* ---------- 输入 ---------- */
QLineEdit, QPlainTextEdit, QTextEdit {{
    background: {p.bg_input};
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 8px 10px;
    selection-background-color: {p.accent};
    selection-color: {p.text_on_accent};
    color: {p.text};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {p.accent};
}}
QLineEdit[role="search"] {{
    border-radius: 16px;
    padding: 6px 14px;
}}
QComboBox {{
    background: {p.bg_input};
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 5px 28px 5px 10px;
    min-height: 20px;
}}
QComboBox:hover {{
    border-color: {p.accent};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {p.text_secondary};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {p.bg_card};
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {p.bg_selected};
    selection-color: {p.text};
}}

/* ---------- 按钮 ---------- */
QPushButton {{
    background: {p.bg_card};
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 6px 14px;
    color: {p.text};
}}
QPushButton:hover {{
    background: {p.bg_hover};
    border-color: {p.border};
}}
QPushButton:pressed {{
    background: {p.bg_selected};
}}
QPushButton:disabled {{
    color: {p.text_disabled};
    background: {p.bg_card};
}}
QPushButton[role="primary"] {{
    background: {p.accent};
    border: 1px solid {p.accent};
    color: {p.text_on_accent};
    font-weight: 600;
}}
QPushButton[role="primary"]:hover {{
    background: {p.accent_hover};
    border-color: {p.accent_hover};
}}
QPushButton[role="primary"]:disabled {{
    background: {p.accent_soft};
    border-color: {p.accent_soft};
    color: {p.text_disabled};
}}
QPushButton[role="ghost"] {{
    background: transparent;
    border: 1px solid transparent;
    color: {p.text_secondary};
}}
QPushButton[role="ghost"]:hover {{
    background: {p.bg_hover};
    color: {p.text};
}}
QPushButton[role="chip"] {{
    background: transparent;
    border: 1px solid {p.border};
    border-radius: 12px;
    padding: 3px 12px;
    font-size: 12px;
    color: {p.text_secondary};
}}
QPushButton[role="chip"]:hover {{
    background: {p.bg_hover};
    color: {p.text};
}}
QPushButton[role="chip"]:checked {{
    background: {p.accent_soft};
    border-color: {p.accent};
    color: {p.accent};
    font-weight: 600;
}}
QPushButton[role="nav"] {{
    background: transparent;
    border: none;
    border-radius: 10px;
    padding: 10px 2px;
    color: {p.text_secondary};
}}
QPushButton[role="nav"]:hover {{
    background: {p.bg_hover};
    color: {p.text};
}}
QPushButton[role="nav"]:checked {{
    background: {p.bg_selected};
    color: {p.accent};
    font-weight: 600;
}}
QPushButton[role="segchip"] {{
    background: {p.bg_card};
    border: 1px solid {p.border};
    border-radius: 10px;
    padding: 8px 12px;
    font-weight: 600;
    color: {p.text};
}}
QPushButton[role="segchip"]:hover {{
    background: {p.bg_hover};
}}
QPushButton[role="segchip"]:checked {{
    background: {p.accent_soft};
    border-color: {p.accent};
    color: {p.accent};
}}
QFrame#navRail {{
    background: transparent;
    border-right: 1px solid {p.divider};
}}
QLabel[role="logo"] {{
    font-weight: 700;
    font-size: 16px;
    padding: 4px 0 10px 0;
    color: {p.accent};
    background: transparent;
}}

/* ---------- 卡片 ---------- */
QFrame[role="card"] {{
    background: {p.bg_card};
    border: 1px solid {p.border};
    border-radius: 10px;
}}
QFrame[role="inset"] {{
    background: {p.bg};
    border: 1px solid {p.divider};
    border-radius: 8px;
}}

/* ---------- 滚动条 ---------- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {p.border};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {p.text_tertiary};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {p.border};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {p.text_tertiary};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
}}

/* ---------- 分割线 ---------- */
QFrame[role="hline"] {{
    border: none;
    border-top: 1px solid {p.divider};
    max-height: 1px;
}}
QFrame[role="vline"] {{
    border: none;
    border-left: 1px solid {p.divider};
    max-width: 1px;
}}

/* ---------- 列表 ---------- */
QListWidget {{
    background: {p.bg_card};
    border: 1px solid {p.border};
    border-radius: 10px;
    padding: 4px;
}}
QListWidget::item {{
    border-radius: 8px;
    padding: 8px 10px;
    margin: 1px 2px;
}}
QListWidget::item:hover {{
    background: {p.bg_hover};
}}
QListWidget::item:selected {{
    background: {p.bg_selected};
    color: {p.text};
}}

/* ---------- 菜单 ---------- */
QMenu {{
    background: {p.bg_card};
    border: 1px solid {p.border};
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: {p.bg_hover};
}}
QMenu::separator {{
    height: 1px;
    background: {p.divider};
    margin: 4px 8px;
}}

/* ---------- Tab ---------- */
QTabWidget::pane {{
    border: none;
}}
QTabBar::tab {{
    background: transparent;
    padding: 6px 14px;
    margin-right: 4px;
    border-radius: 8px;
    color: {p.text_secondary};
}}
QTabBar::tab:hover {{
    background: {p.bg_hover};
}}
QTabBar::tab:selected {{
    background: {p.accent_soft};
    color: {p.accent};
    font-weight: 600;
}}

/* ---------- Tooltip ---------- */
QToolTip {{
    background: {p.bg_card};
    color: {p.text};
    border: 1px solid {p.border};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* ---------- ProgressBar ---------- */
QProgressBar {{
    background: {p.bg_hover};
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {p.accent};
    border-radius: 4px;
}}

/* ---------- CheckBox ---------- */
QCheckBox {{
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {p.border};
    border-radius: 4px;
    background: {p.bg_input};
}}
QCheckBox::indicator:checked {{
    background: {p.accent};
    border-color: {p.accent};
}}

/* ---------- Spinner ---------- */
QLabel[role="skeleton"] {{
    background: {p.bg_hover};
    border-radius: 6px;
}}
"""
