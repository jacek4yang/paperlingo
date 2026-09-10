"""数据库 CRUD、单词去重、历史持久化、设置持久化。"""

from __future__ import annotations

import json
from pathlib import Path

from paperlingo.database.db import Database
from paperlingo.database.migrations import CURRENT_DB_VERSION
from paperlingo.database.repository import Repository
from paperlingo.domain.learning import MasteryStatus, Rating
from paperlingo.learning.review import SimpleScheduler, review_item
from paperlingo.services.settings import AppSettings


def _repo(tmp_path: Path) -> Repository:
    db = Database(tmp_path / "t.db")
    return Repository(db)


def _sample_parsed() -> dict:
    return json.loads(
        (Path(__file__).parent / "fixtures" / "clean.json").read_text(encoding="utf-8")
    )


def test_migration_version(tmp_path: Path) -> None:
    db = Database(tmp_path / "t.db")
    assert db.version() == CURRENT_DB_VERSION
    assert db.is_current()
    db.close()


def test_save_and_reload_analysis(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    parsed = _sample_parsed()
    aid = repo.save_analysis(
        source_text=parsed["source_text"],
        paper_title="A Survey of X",
        paper_doi_or_url="10.1000/xyz",
        prompt_text="PROMPT",
        prompt_version="1.0.0",
        raw_response=json.dumps(parsed),
        parsed=parsed,
    )
    assert aid > 0
    loaded = repo.load_parsed_analysis(aid)
    assert loaded is not None
    analysis, meta = loaded
    assert analysis.source_text.startswith("In this survey")
    assert meta["paper_title"] == "A Survey of X"
    assert meta["prompt_text"] == "PROMPT"
    assert repo.count_analyses() == 1


def test_word_deduplication(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    parsed = _sample_parsed()
    repo.save_analysis(source_text=parsed["source_text"], parsed=parsed, raw_response="{}")
    repo.save_analysis(source_text=parsed["source_text"] + " again", parsed=parsed, raw_response="{}")
    words = repo.list_words()
    curated = [w for w in words if w.lemma == "curate"]
    assert len(curated) == 1
    assert curated[0].occurrences == 2
    assert curated[0].analyses_count == 2


def test_history_search_and_favorite(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    parsed = _sample_parsed()
    aid = repo.save_analysis(
        source_text=parsed["source_text"],
        paper_title="UniqueTitleXYZ",
        parsed=parsed,
    )
    rows = repo.list_analyses(search="UniqueTitleXYZ")
    assert len(rows) == 1
    repo.set_favorite(aid, True)
    favs = repo.list_analyses(favorites_only=True)
    assert len(favs) == 1
    assert favs[0].is_favorite


def test_settings_persistence(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    s = AppSettings(theme="dark", font_scale=1.2, default_depth="deep", default_profile="claude")
    s.save(repo)
    loaded = AppSettings.load(repo)
    assert loaded.theme == "dark"
    assert loaded.font_scale == 1.2
    assert loaded.default_depth == "deep"
    assert loaded.default_profile == "claude"


def test_mastery_and_review_queue(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    parsed = _sample_parsed()
    repo.save_analysis(source_text=parsed["source_text"], parsed=parsed)
    words = repo.list_words()
    wid = words[0].word_id
    repo.set_mastery("word", wid, MasteryStatus.UNFAMILIAR)
    # 默认到期是明天，所以 due_items 目前可能为空；把 due_at 改到过去
    repo.db.conn.execute(
        "UPDATE learning_items SET due_at = datetime('now','localtime','-1 hour') "
        "WHERE item_type = 'word' AND ref_id = ?",
        (wid,),
    )
    repo.db.conn.commit()
    due = repo.due_items()
    assert len(due) >= 1
    ok = review_item(repo, due[0].item_id, Rating.GOOD)
    assert ok
    logs = repo.db.conn.execute("SELECT COUNT(*) c FROM review_logs").fetchone()
    assert logs["c"] == 1


def test_scheduler_again_is_soon() -> None:
    from datetime import datetime

    from paperlingo.learning.review import CardState

    s = SimpleScheduler()
    now = datetime(2026, 1, 1, 12, 0, 0)
    r = s.next(CardState(), Rating.AGAIN, now=now)
    assert r.interval_days < 0.1
    r2 = s.next(CardState(), Rating.EASY, now=now)
    assert r2.interval_days >= 1.0


def test_export_json(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    parsed = _sample_parsed()
    repo.save_analysis(source_text=parsed["source_text"], paper_title="T", parsed=parsed)
    data = repo.export_json()
    assert data["app"] == "PaperLingo"
    assert len(data["analyses"]) == 1
    assert any(w["lemma"] == "curate" for w in data["words"])


def test_list_phrases_and_grammar_after_ingest(tmp_path: Path) -> None:
    """回归：list_phrases/list_grammar 曾查询不存在的 created_at 列，
    知识库页一有短语/语法数据就崩。"""
    repo = _repo(tmp_path)
    parsed = _sample_parsed()
    repo.save_analysis(source_text=parsed["source_text"], parsed=parsed)
    phrases = repo.list_phrases()
    assert phrases, "phrases should be ingested"
    assert all(p.last_seen == "" or len(p.last_seen) >= 8 for p in phrases)
    grammars = repo.list_grammar()
    assert grammars, "grammar patterns should be ingested"
    assert all(g.last_seen == "" or len(g.last_seen) >= 8 for g in grammars)


def test_delete_analysis_keeps_learning_items(tmp_path: Path) -> None:
    """删除 analysis 后，其 occurrences 级联删除，学习条目不受影响。"""
    repo = _repo(tmp_path)
    parsed = _sample_parsed()
    aid = repo.save_analysis(source_text=parsed["source_text"], parsed=parsed)
    repo.delete_analysis(aid)
    assert repo.count_analyses() == 0
    assert repo.db.conn.execute("SELECT COUNT(*) FROM word_occurrences").fetchone()[0] == 0
    # words / learning_items 保留
    assert repo.db.conn.execute("SELECT COUNT(*) FROM words").fetchone()[0] > 0
