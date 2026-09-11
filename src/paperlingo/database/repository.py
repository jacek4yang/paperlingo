"""Data access layer: analyses, knowledge items, settings, drafts, review CRUD.

All SQL is parameterized. The UI layer never touches SQL directly — it calls the
semantic methods on this class.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from paperlingo.database.db import Database
from paperlingo.domain.analysis import PaperAnalysis
from paperlingo.domain.learning import ItemType, MasteryStatus, Rating

logger = logging.getLogger(__name__)

PAGE_SIZE = 50


# ---------------------------------------------------------------------------
# 行数据类（UI 消费的轻量视图）


@dataclass
class AnalysisRow:
    id: int
    paper_id: int | None
    paper_title: str
    source_text: str
    analysis_depth: str
    prompt_version: str
    schema_version: str
    is_favorite: bool
    status: str
    created_at: str
    parsed_json: str = ""


@dataclass
class WordRow:
    word_id: int
    lemma: str
    pos: str
    occurrences: int
    analyses_count: int
    query_count: int = 0
    meanings: list[str] = field(default_factory=list)
    papers: list[str] = field(default_factory=list)
    last_seen: str = ""
    status: str = "unknown"


@dataclass
class PhraseRow:
    phrase_id: int
    text: str
    occurrences: int
    meanings: list[str] = field(default_factory=list)
    last_seen: str = ""
    status: str = "unknown"


@dataclass
class GrammarRow:
    grammar_id: int
    name: str
    name_zh: str
    occurrences: int
    last_seen: str = ""
    status: str = "unknown"


@dataclass
class ExpressionRow:
    expr_id: int
    text: str
    meaning: str
    when_to_use: str
    last_seen: str = ""
    status: str = "unknown"


@dataclass
class ConceptRow:
    concept_id: int
    term: str
    translation: str
    simple_explanation: str
    last_seen: str = ""
    status: str = "unknown"


@dataclass
class ReviewItem:
    item_id: int
    item_type: str
    ref_id: int
    front: str
    back: str
    due_at: str | None
    reps: int


def _analysis_from_parsed(parsed: dict) -> PaperAnalysis:
    return PaperAnalysis.model_validate(parsed)


# ---------------------------------------------------------------------------
# Repository


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db
        #: Last knowledge-ingestion error message, surfaced to callers so that
        #: an ingestion failure is never silently swallowed (analysis row is
        #: still saved; see save_analysis for the atomic strategy).
        self.last_ingest_error: str | None = None

    # ------------------------------------------------------------------
    # settings

    def get_setting(self, key: str, default: str = "") -> str:
        row = self.db.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.db.conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self.db.conn.commit()

    def all_settings(self) -> dict[str, str]:
        rows = self.db.conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}

    # ------------------------------------------------------------------
    # papers

    def _upsert_paper(self, title: str, doi_or_url: str = "", authors: str = "", domain: str = "") -> int | None:
        """Deduplicate by title (or URL); return None when no usable info.

        Runs inside the caller's transaction (no inner commit)."""
        title = title.strip()
        doi_or_url = doi_or_url.strip()
        if not title and not doi_or_url:
            return None
        conn = self.db.conn
        row: sqlite3.Row | None = None
        if doi_or_url:
            row = conn.execute(
                "SELECT id FROM papers WHERE doi_or_url = ?", (doi_or_url,)
            ).fetchone()
        if row is None and title:
            row = conn.execute(
                "SELECT id FROM papers WHERE title = ? AND (doi_or_url = '' OR doi_or_url = ?)",
                (title, doi_or_url),
            ).fetchone()
        if row is not None:
            pid = int(row["id"])
            conn.execute(
                "UPDATE papers SET updated_at = datetime('now','localtime') WHERE id = ?",
                (pid,),
            )
            return pid
        cur = conn.execute(
            "INSERT INTO papers(title, doi_or_url, authors, domain) VALUES(?,?,?,?)",
            (title, doi_or_url, authors.strip(), domain),
        )
        return int(cur.lastrowid)

    def get_paper(self, paper_id: int) -> dict[str, Any] | None:
        row = self.db.conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # analyses
    #
    # Atomicity strategy (documented; see AGENTS.md database contract):
    # saving an analysis (paper upsert + analysis row + knowledge ingestion)
    # runs inside one explicit transaction. If knowledge ingestion fails, only
    # the ingestion part is rolled back (SAVEPOINT) so the parsed analysis is
    # never lost; the error is logged and recorded in `last_ingest_error`.
    # Any other failure rolls back the whole transaction and re-raises.

    def save_analysis(
        self,
        *,
        source_text: str,
        previous_context: str = "",
        following_context: str = "",
        analysis_depth: str = "standard",
        profile_id: str = "generic",
        paper_title: str = "",
        paper_doi_or_url: str = "",
        paper_authors: str = "",
        paper_domain: str = "",
        prompt_text: str = "",
        prompt_version: str = "",
        raw_response: str = "",
        parsed: dict | None = None,
        status: str = "parsed",
    ) -> int:
        """Save one analysis (including the raw response) and accumulate its
        knowledge items into the knowledge base, atomically."""
        conn = self.db.conn
        self.last_ingest_error = None
        parsed_json = json.dumps(parsed, ensure_ascii=False) if parsed else ""
        schema_version = str(parsed.get("schema_version", "")) if parsed else ""
        try:
            conn.execute("BEGIN IMMEDIATE")
            paper_id = self._upsert_paper(paper_title, paper_doi_or_url, paper_authors, paper_domain)
            cur = conn.execute(
                """
                INSERT INTO analyses(
                    paper_id, source_text, previous_context, following_context,
                    analysis_depth, profile_id, prompt_text, prompt_version,
                    raw_response, parsed_json, schema_version, status
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    paper_id, source_text, previous_context, following_context,
                    analysis_depth, profile_id, prompt_text, prompt_version,
                    raw_response, parsed_json, schema_version, status,
                ),
            )
            analysis_id = int(cur.lastrowid)
            if parsed is not None and status == "parsed":
                self._ingest_guarded(analysis_id, parsed)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return analysis_id

    def update_analysis_response(self, analysis_id: int, raw_response: str, parsed: dict | None) -> None:
        conn = self.db.conn
        self.last_ingest_error = None
        parsed_json = json.dumps(parsed, ensure_ascii=False) if parsed else ""
        schema_version = str(parsed.get("schema_version", "")) if parsed else ""
        new_status = "parsed" if parsed else "parse_failed"
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE analyses SET raw_response = ?, parsed_json = ?, schema_version = ?, "
                "status = ?, updated_at = datetime('now','localtime') WHERE id = ?",
                (raw_response, parsed_json, schema_version, new_status, analysis_id),
            )
            if parsed is not None:
                self._ingest_guarded(analysis_id, parsed)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    # ------------------------------------------------------------------
    # Knowledge accumulation: write the PaperAnalysis content into the
    # knowledge tables.

    def _ingest_guarded(self, analysis_id: int, parsed: dict) -> None:
        """Run ingestion inside a SAVEPOINT so an ingestion failure rolls back
        only the knowledge writes (the analysis row itself stays), and record
        the failure explicitly instead of swallowing it."""
        conn = self.db.conn
        conn.execute("SAVEPOINT ingest_sp")
        try:
            self._ingest(analysis_id, _analysis_from_parsed(parsed))
        except Exception as e:
            conn.execute("ROLLBACK TO ingest_sp")
            self.last_ingest_error = f"{type(e).__name__}: {e}"
            logger.exception(
                "knowledge ingestion failed (analysis_id=%s); knowledge writes "
                "rolled back, analysis row kept",
                analysis_id,
            )
        finally:
            conn.execute("RELEASE ingest_sp")

    def _ingest(self, analysis_id: int, a: PaperAnalysis) -> None:
        conn = self.db.conn
        for w in a.words:
            if not w.surface and not w.lemma:
                continue
            lemma = (w.lemma or w.surface).strip().lower()
            pos = w.pos.strip()
            row = conn.execute(
                "SELECT id FROM words WHERE lemma = ? AND pos = ?", (lemma, pos)
            ).fetchone()
            if row is None:
                cur = conn.execute("INSERT INTO words(lemma, pos) VALUES(?,?)", (lemma, pos))
                wid = int(cur.lastrowid)
            else:
                wid = int(row["id"])
            conn.execute(
                """
                INSERT INTO word_occurrences(
                    word_id, analysis_id, surface, meaning_in_context, academic_meaning,
                    phonetic, pos_zh, why_here, collocations_json, common_meanings_json,
                    difficulty, worth_learning
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    wid, analysis_id, w.surface, w.meaning_in_context, w.academic_meaning,
                    w.phonetic, w.pos_zh, w.why_here,
                    json.dumps(w.collocations, ensure_ascii=False),
                    json.dumps(w.common_meanings, ensure_ascii=False),
                    w.difficulty, int(w.worth_learning),
                ),
            )
        for p in a.phrases:
            if not p.text.strip():
                continue
            row = conn.execute("SELECT id FROM phrases WHERE text = ?", (p.text,)).fetchone()
            if row is None:
                cur = conn.execute("INSERT INTO phrases(text) VALUES(?)", (p.text,))
                pid_ = int(cur.lastrowid)
            else:
                pid_ = int(row["id"])
            conn.execute(
                """
                INSERT INTO phrase_occurrences(
                    phrase_id, analysis_id, meaning, explanation, academic_usage,
                    example, example_zh, worth_learning
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                (pid_, analysis_id, p.meaning, p.explanation, p.academic_usage,
                 p.example, p.example_zh, int(p.worth_learning)),
            )
        for g in a.grammar_points:
            if not g.name.strip():
                continue
            row = conn.execute(
                "SELECT id FROM grammar_patterns WHERE name = ?", (g.name,)
            ).fetchone()
            if row is None:
                cur = conn.execute(
                    "INSERT INTO grammar_patterns(name, name_zh) VALUES(?,?)",
                    (g.name, g.name_zh),
                )
                gid = int(cur.lastrowid)
            else:
                gid = int(row["id"])
            conn.execute(
                """
                INSERT INTO grammar_occurrences(
                    grammar_id, analysis_id, source, explanation, why_used_here,
                    simple_example, simple_example_zh, common_mistake, importance
                ) VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (gid, analysis_id, g.source, g.explanation, g.why_used_here,
                 g.simple_example, g.simple_example_zh, g.common_mistake, g.importance),
            )
        for e in a.academic_expressions:
            if not e.text.strip():
                continue
            conn.execute(
                """
                INSERT INTO academic_expressions(text, meaning, usage, when_to_use, example, example_zh, last_analysis_id)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(text) DO UPDATE SET
                    meaning = CASE WHEN excluded.meaning != '' THEN excluded.meaning ELSE academic_expressions.meaning END,
                    last_analysis_id = excluded.last_analysis_id
                """,
                (e.text, e.meaning, e.usage, e.when_to_use, e.example, e.example_zh, analysis_id),
            )
        for c in a.concepts:
            if not c.term.strip():
                continue
            conn.execute(
                """
                INSERT INTO concepts(term, translation, simple_explanation, meaning_in_this_paper, background_needed, last_analysis_id)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(term) DO UPDATE SET
                    translation = CASE WHEN excluded.translation != '' THEN excluded.translation ELSE concepts.translation END,
                    meaning_in_this_paper = excluded.meaning_in_this_paper,
                    last_analysis_id = excluded.last_analysis_id
                """,
                (c.term, c.translation, c.simple_explanation, c.meaning_in_this_paper,
                 int(c.background_needed), analysis_id),
            )
        if a.syntax.structure_summary.strip():
            conn.execute(
                """
                INSERT INTO sentence_patterns(structure_summary, skeleton, last_analysis_id)
                VALUES(?,?,?)
                ON CONFLICT(structure_summary) DO UPDATE SET last_analysis_id = excluded.last_analysis_id
                """,
                (a.syntax.structure_summary, a.syntax.skeleton, analysis_id),
            )

    # ------------------------------------------------------------------
    # analyses 查询

    def list_analyses(
        self,
        *,
        search: str = "",
        paper_id: int | None = None,
        favorites_only: bool = False,
        offset: int = 0,
        limit: int = PAGE_SIZE,
    ) -> list[AnalysisRow]:
        sql = """
            SELECT a.id, a.paper_id, COALESCE(p.title, '') AS paper_title, a.source_text,
                   a.analysis_depth, a.prompt_version, a.schema_version, a.is_favorite,
                   a.status, a.created_at, a.parsed_json
            FROM analyses a LEFT JOIN papers p ON p.id = a.paper_id
            WHERE 1=1
        """
        params: list[Any] = []
        if search:
            sql += " AND (a.source_text LIKE ? OR p.title LIKE ? OR a.raw_response LIKE ? OR a.parsed_json LIKE ?)"
            like = f"%{search}%"
            params += [like, like, like, like]
        if paper_id is not None:
            sql += " AND a.paper_id = ?"
            params.append(paper_id)
        if favorites_only:
            sql += " AND a.is_favorite = 1"
        sql += " ORDER BY a.id DESC LIMIT ? OFFSET ?"
        params += [limit, offset]
        rows = self.db.conn.execute(sql, params).fetchall()
        return [
            AnalysisRow(
                id=r["id"], paper_id=r["paper_id"], paper_title=r["paper_title"],
                source_text=r["source_text"], analysis_depth=r["analysis_depth"],
                prompt_version=r["prompt_version"], schema_version=r["schema_version"],
                is_favorite=bool(r["is_favorite"]), status=r["status"],
                created_at=r["created_at"], parsed_json=r["parsed_json"],
            )
            for r in rows
        ]

    def get_analysis(self, analysis_id: int) -> dict[str, Any] | None:
        row = self.db.conn.execute(
            "SELECT a.*, COALESCE(p.title, '') AS paper_title, p.doi_or_url AS paper_doi, "
            "p.authors AS paper_authors, p.domain AS paper_domain "
            "FROM analyses a LEFT JOIN papers p ON p.id = a.paper_id WHERE a.id = ?",
            (analysis_id,),
        ).fetchone()
        return dict(row) if row else None

    def set_favorite(self, analysis_id: int, favorite: bool) -> None:
        self.db.conn.execute(
            "UPDATE analyses SET is_favorite = ? WHERE id = ?",
            (int(favorite), analysis_id),
        )
        self.db.conn.commit()

    def delete_analysis(self, analysis_id: int) -> None:
        self.db.conn.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
        self.db.conn.commit()

    def count_analyses(self) -> int:
        return int(self.db.conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0])

    def list_papers_with_counts(self) -> list[dict[str, Any]]:
        rows = self.db.conn.execute(
            """
            SELECT p.id, p.title, p.doi_or_url, COUNT(a.id) AS cnt
            FROM papers p JOIN analyses a ON a.paper_id = p.id
            GROUP BY p.id ORDER BY MAX(a.id) DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]

    def load_parsed_analysis(self, analysis_id: int) -> tuple[PaperAnalysis, dict[str, Any]] | None:
        """Restore one complete analysis (used to rebuild the result UI from
        history without another model call)."""
        data = self.get_analysis(analysis_id)
        if not data or not data["parsed_json"]:
            return None
        try:
            parsed = json.loads(data["parsed_json"])
            return _analysis_from_parsed(parsed), data
        except (json.JSONDecodeError, ValueError, ValidationError, TypeError):
            logger.warning(
                "stored analysis %s could not be re-validated; treating as missing",
                analysis_id,
                exc_info=True,
            )
            return None

    # ------------------------------------------------------------------
    # Knowledge-base queries

    def list_words(self, search: str = "", offset: int = 0, limit: int = PAGE_SIZE) -> list[WordRow]:
        sql = """
            SELECT w.id AS word_id, w.lemma, w.pos,
                   COUNT(o.id) AS occurrences,
                   COUNT(DISTINCT o.analysis_id) AS analyses_count,
                   GROUP_CONCAT(o.meaning_in_context, '；') AS meanings,
                   MIN(o.id) AS min_occ
            FROM words w JOIN word_occurrences o ON o.word_id = w.id
            WHERE w.lemma LIKE ?
            GROUP BY w.id, w.lemma, w.pos
            ORDER BY MAX(o.id) DESC LIMIT ? OFFSET ?
        """
        rows = self.db.conn.execute(sql, (f"%{search}%", limit, offset)).fetchall()
        result: list[WordRow] = []
        for r in rows:
            meanings = [m for m in (r["meanings"] or "").split("；") if m]
            papers_rows = self.db.conn.execute(
                """
                SELECT DISTINCT COALESCE(p.title, '') AS t
                FROM word_occurrences o
                JOIN analyses a ON a.id = o.analysis_id
                LEFT JOIN papers p ON p.id = a.paper_id
                WHERE o.word_id = ?
                """,
                (r["word_id"],),
            ).fetchall()
            li = self.get_learning_item(ItemType.WORD.value, r["word_id"])
            result.append(
                WordRow(
                    word_id=r["word_id"], lemma=r["lemma"], pos=r["pos"],
                    occurrences=r["occurrences"], analyses_count=r["analyses_count"],
                    meanings=meanings[:4],
                    papers=[pr["t"] for pr in papers_rows if pr["t"]],
                    status=li["status"] if li else "unknown",
                )
            )
        return result

    def get_word_detail(self, word_id: int) -> dict[str, Any] | None:
        row = self.db.conn.execute("SELECT * FROM words WHERE id = ?", (word_id,)).fetchone()
        if not row:
            return None
        occ = self.db.conn.execute(
            "SELECT o.*, a.created_at FROM word_occurrences o "
            "JOIN analyses a ON a.id = o.analysis_id WHERE o.word_id = ? ORDER BY o.id DESC",
            (word_id,),
        ).fetchall()
        return {"word": dict(row), "occurrences": [dict(o) for o in occ]}

    def list_phrases(self, search: str = "", offset: int = 0, limit: int = PAGE_SIZE) -> list[PhraseRow]:
        rows = self.db.conn.execute(
            """
            SELECT ph.id AS phrase_id, ph.text, COUNT(o.id) AS occurrences,
                   GROUP_CONCAT(o.meaning, '；') AS meanings, MAX(o.id) AS last_id
            FROM phrases ph JOIN phrase_occurrences o ON o.phrase_id = ph.id
            WHERE ph.text LIKE ?
            GROUP BY ph.id, ph.text ORDER BY last_id DESC LIMIT ? OFFSET ?
            """,
            (f"%{search}%", limit, offset),
        ).fetchall()
        result: list[PhraseRow] = []
        for r in rows:
            # occurrence 表无 created_at，取所属分析的时间
            created = self.db.conn.execute(
                "SELECT a.created_at FROM phrase_occurrences o "
                "JOIN analyses a ON a.id = o.analysis_id "
                "WHERE o.phrase_id = ? ORDER BY o.id DESC LIMIT 1",
                (r["phrase_id"],),
            ).fetchone()
            li = self.get_learning_item(ItemType.PHRASE.value, r["phrase_id"])
            result.append(
                PhraseRow(
                    phrase_id=r["phrase_id"], text=r["text"], occurrences=r["occurrences"],
                    meanings=[m for m in (r["meanings"] or "").split("；") if m][:3],
                    last_seen=created["created_at"] if created else "",
                    status=li["status"] if li else "unknown",
                )
            )
        return result

    def list_grammar(self, search: str = "", offset: int = 0, limit: int = PAGE_SIZE) -> list[GrammarRow]:
        rows = self.db.conn.execute(
            """
            SELECT g.id AS grammar_id, g.name, g.name_zh, COUNT(o.id) AS occurrences,
                   MAX(o.id) AS last_id
            FROM grammar_patterns g JOIN grammar_occurrences o ON o.grammar_id = g.id
            WHERE g.name LIKE ? OR g.name_zh LIKE ?
            GROUP BY g.id, g.name, g.name_zh ORDER BY last_id DESC LIMIT ? OFFSET ?
            """,
            (f"%{search}%", f"%{search}%", limit, offset),
        ).fetchall()
        result: list[GrammarRow] = []
        for r in rows:
            # occurrence 表无 created_at，取所属分析的时间
            created = self.db.conn.execute(
                "SELECT a.created_at FROM grammar_occurrences o "
                "JOIN analyses a ON a.id = o.analysis_id "
                "WHERE o.grammar_id = ? ORDER BY o.id DESC LIMIT 1",
                (r["grammar_id"],),
            ).fetchone()
            li = self.get_learning_item(ItemType.GRAMMAR.value, r["grammar_id"])
            result.append(
                GrammarRow(
                    grammar_id=r["grammar_id"], name=r["name"], name_zh=r["name_zh"],
                    occurrences=r["occurrences"],
                    last_seen=created["created_at"] if created else "",
                    status=li["status"] if li else "unknown",
                )
            )
        return result

    def list_expressions(self, search: str = "", offset: int = 0, limit: int = PAGE_SIZE) -> list[ExpressionRow]:
        rows = self.db.conn.execute(
            "SELECT id, text, meaning, when_to_use, last_analysis_id FROM academic_expressions "
            "WHERE text LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (f"%{search}%", limit, offset),
        ).fetchall()
        result: list[ExpressionRow] = []
        for r in rows:
            created = None
            if r["last_analysis_id"]:
                created = self.db.conn.execute(
                    "SELECT created_at FROM analyses WHERE id = ?", (r["last_analysis_id"],)
                ).fetchone()
            li = self.get_learning_item(ItemType.EXPRESSION.value, r["id"])
            result.append(
                ExpressionRow(
                    expr_id=r["id"], text=r["text"], meaning=r["meaning"],
                    when_to_use=r["when_to_use"],
                    last_seen=created["created_at"] if created else "",
                    status=li["status"] if li else "unknown",
                )
            )
        return result

    def list_concepts(self, search: str = "", offset: int = 0, limit: int = PAGE_SIZE) -> list[ConceptRow]:
        rows = self.db.conn.execute(
            "SELECT id, term, translation, simple_explanation, last_analysis_id FROM concepts "
            "WHERE term LIKE ? OR translation LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (f"%{search}%", f"%{search}%", limit, offset),
        ).fetchall()
        result: list[ConceptRow] = []
        for r in rows:
            created = None
            if r["last_analysis_id"]:
                created = self.db.conn.execute(
                    "SELECT created_at FROM analyses WHERE id = ?", (r["last_analysis_id"],)
                ).fetchone()
            li = self.get_learning_item(ItemType.CONCEPT.value, r["id"])
            result.append(
                ConceptRow(
                    concept_id=r["id"], term=r["term"], translation=r["translation"],
                    simple_explanation=r["simple_explanation"],
                    last_seen=created["created_at"] if created else "",
                    status=li["status"] if li else "unknown",
                )
            )
        return result

    def list_sentence_patterns(self, offset: int = 0, limit: int = PAGE_SIZE) -> list[dict[str, Any]]:
        rows = self.db.conn.execute(
            "SELECT id, structure_summary, skeleton, last_analysis_id FROM sentence_patterns "
            "ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Knowledge detail getters (semantic methods for the UI; no raw SQL in UI)

    def get_phrase_detail(self, phrase_id: int) -> dict[str, Any] | None:
        conn = self.db.conn
        main = conn.execute("SELECT text FROM phrases WHERE id = ?", (phrase_id,)).fetchone()
        if not main:
            return None
        rows = conn.execute(
            "SELECT meaning, explanation, academic_usage, example, example_zh, worth_learning "
            "FROM phrase_occurrences WHERE phrase_id = ? ORDER BY id DESC",
            (phrase_id,),
        ).fetchall()
        return {"text": main["text"], "occurrences": [dict(r) for r in rows]}

    def get_grammar_detail(self, grammar_id: int) -> dict[str, Any] | None:
        conn = self.db.conn
        main = conn.execute(
            "SELECT name, name_zh FROM grammar_patterns WHERE id = ?", (grammar_id,)
        ).fetchone()
        if not main:
            return None
        rows = conn.execute(
            "SELECT source, explanation, why_used_here, simple_example, simple_example_zh, "
            "common_mistake, importance FROM grammar_occurrences WHERE grammar_id = ? "
            "ORDER BY id DESC",
            (grammar_id,),
        ).fetchall()
        return {
            "name": main["name"],
            "name_zh": main["name_zh"],
            "occurrences": [dict(r) for r in rows],
        }

    def get_expression_detail(self, expr_id: int) -> dict[str, Any] | None:
        row = self.db.conn.execute(
            "SELECT text, meaning, usage, when_to_use, example, example_zh, last_analysis_id "
            "FROM academic_expressions WHERE id = ?",
            (expr_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_concept_detail(self, concept_id: int) -> dict[str, Any] | None:
        row = self.db.conn.execute(
            "SELECT term, translation, simple_explanation, meaning_in_this_paper, "
            "background_needed, last_analysis_id FROM concepts WHERE id = ?",
            (concept_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_sentence_pattern(self, pattern_id: int) -> dict[str, Any] | None:
        row = self.db.conn.execute(
            "SELECT id, structure_summary, skeleton, last_analysis_id "
            "FROM sentence_patterns WHERE id = ?",
            (pattern_id,),
        ).fetchone()
        return dict(row) if row else None

    def find_knowledge_item_id(self, item_type: str, key: str) -> int | None:
        """Look up a knowledge item id by its identity key.

        Words are keyed by lemma (case-insensitive); phrases by exact text.
        Returns None when no matching item exists.
        """
        if item_type == ItemType.WORD.value:
            row = self.db.conn.execute(
                "SELECT id FROM words WHERE LOWER(lemma) = LOWER(?)", (key,)
            ).fetchone()
        elif item_type == ItemType.PHRASE.value:
            row = self.db.conn.execute(
                "SELECT id FROM phrases WHERE text = ?", (key,)
            ).fetchone()
        else:
            return None
        return int(row["id"]) if row else None

    def get_word_occurrence_count(self, word_id: int) -> int:
        row = self.db.conn.execute(
            "SELECT COUNT(*) FROM word_occurrences WHERE word_id = ?", (word_id,)
        ).fetchone()
        return int(row[0])

    # ------------------------------------------------------------------
    # drafts (unfinished reading state, SQLite-backed for portability)

    def save_draft(self, payload_json: str) -> None:
        self.db.conn.execute(
            """
            INSERT INTO drafts(id, payload, updated_at) VALUES(1, ?, datetime('now','localtime'))
            ON CONFLICT(id) DO UPDATE SET
                payload = excluded.payload, updated_at = excluded.updated_at
            """,
            (payload_json,),
        )
        self.db.conn.commit()

    def load_draft(self) -> str | None:
        row = self.db.conn.execute("SELECT payload FROM drafts WHERE id = 1").fetchone()
        return row["payload"] if row else None

    def clear_draft(self) -> None:
        self.db.conn.execute("DELETE FROM drafts WHERE id = 1")
        self.db.conn.commit()

    # ------------------------------------------------------------------
    # learning items / review

    def get_learning_item(self, item_type: str, ref_id: int) -> sqlite3.Row | None:
        return self.db.conn.execute(
            "SELECT * FROM learning_items WHERE item_type = ? AND ref_id = ?",
            (item_type, ref_id),
        ).fetchone()

    def set_mastery(self, item_type: str, ref_id: int, status: MasteryStatus) -> None:
        """Set mastery status; unfamiliar/hard enter the review queue (due tomorrow)."""
        conn = self.db.conn
        existing = self.get_learning_item(item_type, ref_id)
        if existing is None:
            conn.execute(
                """
                INSERT INTO learning_items(item_type, ref_id, status, due_at)
                VALUES(?,?,?,CASE WHEN ? IN ('unfamiliar','hard')
                       THEN datetime('now','localtime','+1 day') ELSE NULL END)
                """,
                (item_type, ref_id, status.value, status.value),
            )
        else:
            conn.execute(
                """
                UPDATE learning_items SET status = ?,
                    due_at = CASE WHEN ? IN ('unfamiliar','hard')
                            THEN COALESCE(due_at, datetime('now','localtime','+1 day'))
                            ELSE NULL END,
                    updated_at = datetime('now','localtime')
                WHERE item_type = ? AND ref_id = ?
                """,
                (status.value, status.value, item_type, ref_id),
            )
        conn.commit()

    def due_items(self, limit: int = 20) -> list[ReviewItem]:
        """Due review items (unfamiliar/hard and past due)."""
        rows = self.db.conn.execute(
            """
            SELECT li.id, li.item_type, li.ref_id, li.due_at, li.reps
            FROM learning_items li
            WHERE li.status IN ('unfamiliar','hard')
              AND (li.due_at IS NULL OR li.due_at <= datetime('now','localtime'))
            ORDER BY COALESCE(li.due_at, '') LIMIT ?
            """,
            (limit,),
        ).fetchall()
        items: list[ReviewItem] = []
        for r in rows:
            front, back = self._review_content(r["item_type"], r["ref_id"])
            if front is None:
                continue
            items.append(
                ReviewItem(
                    item_id=r["id"], item_type=r["item_type"], ref_id=r["ref_id"],
                    front=front, back=back, due_at=r["due_at"], reps=r["reps"],
                )
            )
        return items

    def _review_content(self, item_type: str, ref_id: int) -> tuple[str | None, str]:
        conn = self.db.conn
        if item_type == ItemType.WORD.value:
            row = conn.execute("SELECT lemma, pos FROM words WHERE id = ?", (ref_id,)).fetchone()
            if not row:
                return None, ""
            occ = conn.execute(
                "SELECT meaning_in_context FROM word_occurrences WHERE word_id = ? AND meaning_in_context != '' LIMIT 1",
                (ref_id,),
            ).fetchone()
            return row["lemma"], occ["meaning_in_context"] if occ else ""
        if item_type == ItemType.PHRASE.value:
            row = conn.execute("SELECT text FROM phrases WHERE id = ?", (ref_id,)).fetchone()
            if not row:
                return None, ""
            occ = conn.execute(
                "SELECT meaning FROM phrase_occurrences WHERE phrase_id = ? AND meaning != '' LIMIT 1",
                (ref_id,),
            ).fetchone()
            return row["text"], occ["meaning"] if occ else ""
        if item_type == ItemType.GRAMMAR.value:
            row = conn.execute(
                "SELECT name, name_zh FROM grammar_patterns WHERE id = ?", (ref_id,)
            ).fetchone()
            if not row:
                return None, ""
            return row["name_zh"] or row["name"], row["name"]
        if item_type == ItemType.EXPRESSION.value:
            row = conn.execute(
                "SELECT text, meaning FROM academic_expressions WHERE id = ?", (ref_id,)
            ).fetchone()
            return (row["text"], row["meaning"]) if row else (None, "")
        if item_type == ItemType.CONCEPT.value:
            row = conn.execute(
                "SELECT term, translation FROM concepts WHERE id = ?", (ref_id,)
            ).fetchone()
            return (row["term"], row["translation"]) if row else (None, "")
        return None, ""

    def get_card_state(self, learning_item_id: int) -> dict[str, Any] | None:
        """Scheduling state of one learning item (consumed by the Scheduler)."""
        row = self.db.conn.execute(
            "SELECT stability, difficulty, reps, lapses FROM learning_items WHERE id = ?",
            (learning_item_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "stability": float(row["stability"] or 0.0),
            "difficulty": float(row["difficulty"] or 0.0),
            "reps": int(row["reps"] or 0),
            "lapses": int(row["lapses"] or 0),
        }

    def log_review(self, learning_item_id: int, rating: Rating, scheduler_result: dict[str, Any]) -> None:
        """Persist a review log and write the scheduler result back to learning_items."""
        conn = self.db.conn
        conn.execute(
            "INSERT INTO review_logs(learning_item_id, rating) VALUES(?,?)",
            (learning_item_id, rating.value),
        )
        conn.execute(
            """
            UPDATE learning_items SET
                stability = ?, difficulty = ?, reps = reps + 1,
                lapses = lapses + ?, due_at = ?, last_review_at = datetime('now','localtime'),
                updated_at = datetime('now','localtime')
            WHERE id = ?
            """,
            (
                scheduler_result.get("stability", 0.0),
                scheduler_result.get("difficulty", 0.0),
                1 if rating == Rating.AGAIN else 0,
                scheduler_result.get("due_at"),
                learning_item_id,
            ),
        )
        conn.commit()

    # ------------------------------------------------------------------
    # export

    def export_json(self) -> dict[str, Any]:
        conn = self.db.conn

        def dump(sql: str) -> list[dict[str, Any]]:
            return [dict(r) for r in conn.execute(sql).fetchall()]

        return {
            "app": "PaperLingo",
            "exported_at": conn.execute("SELECT datetime('now','localtime') AS t").fetchone()["t"],
            "papers": dump("SELECT * FROM papers ORDER BY id"),
            "analyses": dump("SELECT id, paper_id, source_text, analysis_depth, schema_version, created_at FROM analyses ORDER BY id"),
            "words": dump(
                "SELECT w.lemma, w.pos, COUNT(o.id) AS occurrences FROM words w "
                "LEFT JOIN word_occurrences o ON o.word_id = w.id GROUP BY w.id ORDER BY w.lemma"
            ),
            "phrases": dump(
                "SELECT p.text, COUNT(o.id) AS occurrences FROM phrases p "
                "LEFT JOIN phrase_occurrences o ON o.phrase_id = p.id GROUP BY p.id ORDER BY p.text"
            ),
            "grammar_patterns": dump(
                "SELECT g.name, g.name_zh, COUNT(o.id) AS occurrences FROM grammar_patterns g "
                "LEFT JOIN grammar_occurrences o ON o.grammar_id = g.id GROUP BY g.id ORDER BY g.name"
            ),
            "academic_expressions": dump("SELECT text, meaning, when_to_use FROM academic_expressions ORDER BY text"),
            "concepts": dump("SELECT term, translation, simple_explanation FROM concepts ORDER BY term"),
            "learning_items": dump("SELECT item_type, ref_id, status, reps, lapses, due_at FROM learning_items"),
            "review_logs": dump("SELECT learning_item_id, rating, reviewed_at FROM review_logs"),
            "settings": self.all_settings(),
        }

    # ------------------------------------------------------------------
    # statistics (learner profile)

    def knowledge_stats(self) -> dict[str, int]:
        conn = self.db.conn

        def count1(sql: str) -> int:
            return int(conn.execute(sql).fetchone()[0])

        return {
            "words": count1("SELECT COUNT(*) FROM words"),
            "phrases": count1("SELECT COUNT(*) FROM phrases"),
            "grammar": count1("SELECT COUNT(*) FROM grammar_patterns"),
            "expressions": count1("SELECT COUNT(*) FROM academic_expressions"),
            "concepts": count1("SELECT COUNT(*) FROM concepts"),
            "analyses": count1("SELECT COUNT(*) FROM analyses"),
            "learning": count1("SELECT COUNT(*) FROM learning_items WHERE status IN ('unfamiliar','hard')"),
            "mastered": count1("SELECT COUNT(*) FROM learning_items WHERE status = 'known'"),
        }

    def weak_learning_counts(self) -> list[sqlite3.Row]:
        """Count learning items per item type among the weak statuses
        (unfamiliar/hard). Used to build the learner profile for prompts."""
        return self.db.conn.execute(
            "SELECT li.item_type, COUNT(*) AS c FROM learning_items li "
            "WHERE li.status IN ('unfamiliar','hard') GROUP BY li.item_type"
        ).fetchall()
