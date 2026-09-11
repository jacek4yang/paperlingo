"""Database lifecycle: portable path, idempotent close, migrations, atomic
transactions."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

from paperlingo.database.db import Database, DatabaseOpenError, application_data_dir
from paperlingo.database.migrations import CURRENT_DB_VERSION, MIGRATION_1
from paperlingo.database.repository import Repository


def _repo(tmp_path: Path) -> Repository:
    return Repository(Database(tmp_path / "t.db"))


def _sample_parsed() -> dict:
    return json.loads(
        (Path(__file__).parent / "fixtures" / "clean.json").read_text(encoding="utf-8")
    )


# ---------------------------------------------------------------------------
# Portable path


def test_development_data_dir_is_project_local() -> None:
    data_dir = application_data_dir()
    # Deterministic project-local location: the repository root, identified by
    # pyproject.toml.
    assert (data_dir / "pyproject.toml").exists()


def test_frozen_data_dir_is_beside_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_exe = tmp_path / "PaperLingo" / "PaperLingo.exe"
    fake_exe.parent.mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    assert application_data_dir() == fake_exe.parent
    # The packaged invariant: DB beside the exe.
    assert application_data_dir() / "paperlingo.db" == fake_exe.parent / "paperlingo.db"


# ---------------------------------------------------------------------------
# Open safety


def test_unwritable_directory_raises_database_open_error(tmp_path: Path) -> None:
    # Parent "path" is a file, so creating the DB is impossible.
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(DatabaseOpenError):
        Database(blocker / "paperlingo.db")


# ---------------------------------------------------------------------------
# Close lifecycle


def test_close_is_idempotent(tmp_path: Path) -> None:
    db = Database(tmp_path / "t.db")
    db.close()
    db.close()  # must not raise
    with pytest.raises(RuntimeError):
        _ = db.conn


def test_close_commits_pending_work(tmp_path: Path) -> None:
    db = Database(tmp_path / "t.db")
    repo = Repository(db)
    repo.set_setting("theme", "dark")
    db.close()

    db2 = Database(tmp_path / "t.db")
    assert db2.conn.execute("SELECT value FROM settings WHERE key='theme'").fetchone()["value"] == "dark"
    db2.close()


# ---------------------------------------------------------------------------
# Migrations


def test_upgrade_from_v1_preserves_data(tmp_path: Path) -> None:
    """A v1 database (no drafts table) must upgrade in place without losing
    existing user data."""
    path = tmp_path / "old.db"
    conn = sqlite3.connect(str(path))
    conn.executescript(MIGRATION_1)
    conn.execute("INSERT INTO papers(title) VALUES('Legacy paper')")
    conn.execute(
        "INSERT INTO analyses(source_text) VALUES('Legacy analysis')"
    )
    conn.execute("INSERT INTO words(lemma, pos) VALUES('curate', 'verb')")
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()

    db = Database(path)
    assert db.version() == CURRENT_DB_VERSION
    assert db.is_current()
    # Old data intact
    assert db.conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0] == 1
    assert db.conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0] == 1
    assert db.conn.execute("SELECT COUNT(*) FROM words").fetchone()[0] == 1
    # New drafts table exists and works
    repo = Repository(db)
    repo.save_draft("{}")
    assert repo.load_draft() == "{}"
    db.close()


# ---------------------------------------------------------------------------
# Transactions / atomicity


def test_ingest_failure_keeps_analysis_and_rolls_back_knowledge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)

    def _boom(self, analysis_id, parsed):
        raise ValueError("simulated ingestion failure")

    monkeypatch.setattr(Repository, "_ingest", _boom)
    parsed = _sample_parsed()
    aid = repo.save_analysis(source_text=parsed["source_text"], parsed=parsed)
    # Analysis row is kept, knowledge writes are rolled back, failure recorded.
    assert repo.count_analyses() == 1
    assert repo.db.conn.execute("SELECT COUNT(*) FROM words").fetchone()[0] == 0
    assert repo.last_ingest_error is not None
    assert "simulated ingestion failure" in repo.last_ingest_error

    # A later successful save works normally (transaction state is clean).
    monkeypatch.undo()
    aid2 = repo.save_analysis(source_text=parsed["source_text"], parsed=parsed)
    assert aid2 == aid + 1
    assert repo.last_ingest_error is None
    assert repo.db.conn.execute("SELECT COUNT(*) FROM words").fetchone()[0] > 0


def test_save_failure_rolls_back_whole_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)

    def _boom(self, *args, **kwargs):
        raise RuntimeError("simulated insert failure")

    monkeypatch.setattr(Repository, "_ingest_guarded", _boom)
    parsed = _sample_parsed()
    with pytest.raises(RuntimeError):
        repo.save_analysis(source_text=parsed["source_text"], parsed=parsed)
    # Nothing persisted: no analysis, no paper.
    assert repo.count_analyses() == 0
    assert repo.db.conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0] == 0
