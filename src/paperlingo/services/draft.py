"""Unfinished reading-state persistence (drafts).

Drafts live in the portable SQLite database (drafts table) so the packaged app
keeps all user state beside the executable. A lost draft is acceptable; losing
the analysis must never happen — so write failures are logged but never crash
the main flow.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from paperlingo.database.repository import Repository

logger = logging.getLogger(__name__)


class DraftStore:
    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    def save(self, payload: dict[str, Any]) -> None:
        try:
            self._repo.save_draft(json.dumps(payload, ensure_ascii=False))
        except Exception:
            # Draft loss is acceptable; never interrupt the main flow.
            logger.warning("failed to persist draft", exc_info=True)

    def load(self) -> dict[str, Any] | None:
        raw = self._repo.load_draft()
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("stored draft is not valid JSON; discarding")
            return None
        return data if isinstance(data, dict) else None

    def clear(self) -> None:
        try:
            self._repo.clear_draft()
        except Exception:
            logger.warning("failed to clear draft", exc_info=True)
