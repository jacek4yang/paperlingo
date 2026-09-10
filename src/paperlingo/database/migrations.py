"""数据库版本迁移机制。

每次结构变更追加一个 migration 函数，MIGRATIONS 顺序即版本号（从 1 开始）。
user_version 记录当前版本，启动时自动按序执行缺失的迁移。
"""

from __future__ import annotations

import sqlite3

MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT '',
    doi_or_url TEXT NOT NULL DEFAULT '',
    authors TEXT NOT NULL DEFAULT '',
    domain TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_papers_title ON papers(title);

CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER REFERENCES papers(id) ON DELETE SET NULL,
    source_text TEXT NOT NULL,
    previous_context TEXT NOT NULL DEFAULT '',
    following_context TEXT NOT NULL DEFAULT '',
    analysis_depth TEXT NOT NULL DEFAULT 'standard',
    profile_id TEXT NOT NULL DEFAULT 'generic',
    prompt_text TEXT NOT NULL DEFAULT '',
    prompt_version TEXT NOT NULL DEFAULT '',
    raw_response TEXT NOT NULL DEFAULT '',
    parsed_json TEXT NOT NULL DEFAULT '',
    schema_version TEXT NOT NULL DEFAULT '',
    is_favorite INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'parsed',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_analyses_paper ON analyses(paper_id);
CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analyses_status ON analyses(status);

CREATE TABLE IF NOT EXISTS words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lemma TEXT NOT NULL,
    pos TEXT NOT NULL DEFAULT '',
    UNIQUE(lemma, pos)
);

CREATE TABLE IF NOT EXISTS word_occurrences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
    analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    surface TEXT NOT NULL DEFAULT '',
    meaning_in_context TEXT NOT NULL DEFAULT '',
    academic_meaning TEXT NOT NULL DEFAULT '',
    phonetic TEXT NOT NULL DEFAULT '',
    pos_zh TEXT NOT NULL DEFAULT '',
    why_here TEXT NOT NULL DEFAULT '',
    collocations_json TEXT NOT NULL DEFAULT '[]',
    common_meanings_json TEXT NOT NULL DEFAULT '[]',
    difficulty INTEGER NOT NULL DEFAULT 3,
    worth_learning INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_word_occ_word ON word_occurrences(word_id);
CREATE INDEX IF NOT EXISTS idx_word_occ_analysis ON word_occurrences(analysis_id);

CREATE TABLE IF NOT EXISTS phrases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS phrase_occurrences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phrase_id INTEGER NOT NULL REFERENCES phrases(id) ON DELETE CASCADE,
    analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    meaning TEXT NOT NULL DEFAULT '',
    explanation TEXT NOT NULL DEFAULT '',
    academic_usage TEXT NOT NULL DEFAULT '',
    example TEXT NOT NULL DEFAULT '',
    example_zh TEXT NOT NULL DEFAULT '',
    worth_learning INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_phrase_occ_phrase ON phrase_occurrences(phrase_id);
CREATE INDEX IF NOT EXISTS idx_phrase_occ_analysis ON phrase_occurrences(analysis_id);

CREATE TABLE IF NOT EXISTS grammar_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    name_zh TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS grammar_occurrences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grammar_id INTEGER NOT NULL REFERENCES grammar_patterns(id) ON DELETE CASCADE,
    analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    source TEXT NOT NULL DEFAULT '',
    explanation TEXT NOT NULL DEFAULT '',
    why_used_here TEXT NOT NULL DEFAULT '',
    simple_example TEXT NOT NULL DEFAULT '',
    simple_example_zh TEXT NOT NULL DEFAULT '',
    common_mistake TEXT NOT NULL DEFAULT '',
    importance INTEGER NOT NULL DEFAULT 3
);
CREATE INDEX IF NOT EXISTS idx_grammar_occ_grammar ON grammar_occurrences(grammar_id);
CREATE INDEX IF NOT EXISTS idx_grammar_occ_analysis ON grammar_occurrences(analysis_id);

CREATE TABLE IF NOT EXISTS academic_expressions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL UNIQUE,
    meaning TEXT NOT NULL DEFAULT '',
    usage TEXT NOT NULL DEFAULT '',
    when_to_use TEXT NOT NULL DEFAULT '',
    example TEXT NOT NULL DEFAULT '',
    example_zh TEXT NOT NULL DEFAULT '',
    last_analysis_id INTEGER REFERENCES analyses(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS concepts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term TEXT NOT NULL UNIQUE,
    translation TEXT NOT NULL DEFAULT '',
    simple_explanation TEXT NOT NULL DEFAULT '',
    meaning_in_this_paper TEXT NOT NULL DEFAULT '',
    background_needed INTEGER NOT NULL DEFAULT 0,
    last_analysis_id INTEGER REFERENCES analyses(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS sentence_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    structure_summary TEXT NOT NULL UNIQUE,
    skeleton TEXT NOT NULL DEFAULT '',
    last_analysis_id INTEGER REFERENCES analyses(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS learning_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_type TEXT NOT NULL,
    ref_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'unknown',
    stability REAL NOT NULL DEFAULT 0,
    difficulty REAL NOT NULL DEFAULT 0,
    reps INTEGER NOT NULL DEFAULT 0,
    lapses INTEGER NOT NULL DEFAULT 0,
    due_at TEXT,
    last_review_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(item_type, ref_id)
);
CREATE INDEX IF NOT EXISTS idx_learning_due ON learning_items(due_at);
CREATE INDEX IF NOT EXISTS idx_learning_type ON learning_items(item_type);

CREATE TABLE IF NOT EXISTS review_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learning_item_id INTEGER NOT NULL REFERENCES learning_items(id) ON DELETE CASCADE,
    rating TEXT NOT NULL,
    reviewed_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_review_logs_item ON review_logs(learning_item_id);
"""

#: 迁移列表：索引即版本号 - 1。MIGRATIONS[0] 把数据库从 0 升到 1。
MIGRATIONS: list[str] = [MIGRATION_1]

CURRENT_DB_VERSION = len(MIGRATIONS)


def migrate(conn: sqlite3.Connection) -> None:
    """把 conn 指向的数据库升级到最新版本。"""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version in range(current, CURRENT_DB_VERSION):
        conn.executescript(MIGRATIONS[version])
        conn.execute(f"PRAGMA user_version = {version + 1}")
    conn.commit()
