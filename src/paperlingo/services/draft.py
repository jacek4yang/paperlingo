"""草稿自动保存：防止页面切换 / 异常退出丢失未完成的阅读任务。

以 JSON 文件形式保存在用户数据目录，写入失败静默（草稿丢失可接受，
但不能影响主流程）。
"""

from __future__ import annotations

import json
from contextlib import suppress
from pathlib import Path
from typing import Any

from paperlingo.database.db import default_data_dir

DRAFT_FILENAME = "draft.json"


class DraftStore:
    def __init__(self, directory: Path | None = None) -> None:
        self.path = (directory or default_data_dir()) / DRAFT_FILENAME

    def save(self, payload: dict[str, Any]) -> None:
        # 草稿丢失可接受：文件 IO 失败不中断主流程
        with suppress(OSError, TypeError, ValueError):
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )

    def load(self) -> dict[str, Any] | None:
        try:
            if not self.path.exists():
                return None
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def clear(self) -> None:
        with suppress(OSError):
            self.path.unlink(missing_ok=True)
