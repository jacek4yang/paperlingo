"""Application settings, persisted in the SQLite settings table.

Provides typed access; unknown or missing values fall back to defaults. Note:
there is deliberately no database-path setting — the database location is an
explicit portable contract (beside the executable; see AGENTS.md).
"""

from __future__ import annotations

from dataclasses import dataclass

from paperlingo.database.repository import Repository
from paperlingo.domain.analysis import DEPTH_LABELS, AnalysisDepth
from paperlingo.prompt.profiles import DEFAULT_PROFILE_ID

THEME_SYSTEM = "system"
THEME_LIGHT = "light"
THEME_DARK = "dark"

THEME_LABELS = {THEME_SYSTEM: "跟随系统", THEME_LIGHT: "浅色", THEME_DARK: "深色"}


@dataclass
class AppSettings:
    theme: str = THEME_SYSTEM
    font_scale: float = 1.0
    default_depth: AnalysisDepth = "standard"
    default_profile: str = DEFAULT_PROFILE_ID

    @classmethod
    def load(cls, repo: Repository) -> AppSettings:
        s = cls()

        def get(key: str, default: str) -> str:
            return repo.get_setting(key, default)

        s.theme = get("theme", s.theme)
        try:
            s.font_scale = max(0.8, min(1.4, float(get("font_scale", "1.0"))))
        except ValueError:
            s.font_scale = 1.0
        depth = get("default_depth", s.default_depth)
        s.default_depth = depth if depth in DEPTH_LABELS else "standard"  # type: ignore[assignment]
        s.default_profile = get("default_profile", s.default_profile)
        return s

    def save(self, repo: Repository) -> None:
        repo.set_setting("theme", self.theme)
        repo.set_setting("font_scale", str(self.font_scale))
        repo.set_setting("default_depth", self.default_depth)
        repo.set_setting("default_profile", self.default_profile)
