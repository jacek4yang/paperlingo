"""草稿自动保存。"""

from pathlib import Path

from paperlingo.services.draft import DraftStore


def test_save_load_clear(tmp_path: Path) -> None:
    store = DraftStore(tmp_path)
    store.save({"source_text": "hello world", "paper_title": "T"})
    data = store.load()
    assert data is not None
    assert data["source_text"] == "hello world"
    store.clear()
    assert store.load() is None


def test_corrupt_file_returns_none(tmp_path: Path) -> None:
    store = DraftStore(tmp_path)
    store.path.write_text("{not json", encoding="utf-8")
    assert store.load() is None
