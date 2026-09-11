"""Draft persistence (SQLite-backed, portable)."""

from __future__ import annotations

import json
from pathlib import Path

from paperlingo.database.db import Database
from paperlingo.database.repository import Repository
from paperlingo.services.draft import DraftStore


def _store(tmp_path: Path) -> DraftStore:
    repo = Repository(Database(tmp_path / "t.db"))
    return DraftStore(repo)


def test_save_load_clear(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save({"source_text": "hello world", "paper_title": "T"})
    data = store.load()
    assert data is not None
    assert data["source_text"] == "hello world"
    store.clear()
    assert store.load() is None


def test_corrupt_payload_returns_none(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store._repo.save_draft("{not json")
    assert store.load() is None


def test_draft_survives_reopen(tmp_path: Path) -> None:
    repo = Repository(Database(tmp_path / "t.db"))
    DraftStore(repo).save({"source_text": "persisted"})

    repo2 = Repository(Database(tmp_path / "t.db"))
    data = DraftStore(repo2).load()
    assert data is not None and data["source_text"] == "persisted"


def test_draft_roundtrip_keeps_chinese_payload(tmp_path: Path) -> None:
    store = _store(tmp_path)
    payload = {"source_text": "Hello", "note": "中文内容保持原样"}
    store.save(payload)
    loaded = store.load()
    assert loaded == payload
    # Payload is stored as JSON text (ensure_ascii=False) in the drafts table.
    raw = json.loads(store._repo.load_draft() or "null")
    assert raw["note"] == "中文内容保持原样"
