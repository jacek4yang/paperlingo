"""Structured schema for AI responses (Pydantic v2).

Design principles:
- The AI returns structured JSON only; never HTML / CSS / Markdown / executable code.
- All fields tolerate the complexity real-world web AIs can reliably produce: almost
  everything is optional, defaulting to empty list / empty string / null. The AI is
  forbidden from fabricating content just to fill the schema.
- The schema carries a version (SCHEMA_VERSION); future upgrades migrate here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: Current schema version. The prompt asks the AI to echo it back.
SCHEMA_VERSION = "1.0"

#: Maximum length of a single text field (defense against abnormal output)
MAX_TEXT_LENGTH = 4000
#: Maximum number of entries in list-like fields
MAX_ITEMS = 100


class _Base(BaseModel):
    """Common base: unknown extra fields tolerated (lenient), over-long strings
    truncated at the field level by validators where needed."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class Translation(_Base):
    natural: str = ""
    literal: str = ""
    core_meaning: str = ""
    translation_notes: list[str] = Field(default_factory=list)


class SentenceOverview(_Base):
    difficulty: int = Field(default=3, ge=1, le=5)
    difficulty_reason: str = ""
    sentence_type: str = ""
    one_sentence_explanation: str = ""
    reading_strategy: str = ""


class SyntaxSegment(_Base):
    """One fragment of the original sentence and its grammatical role. `text`
    must be findable in the source text (used for interactive highlighting)."""

    text: str = ""
    role: str = ""
    role_zh: str = ""
    explanation: str = ""


class Clause(_Base):
    text: str = ""
    type: str = ""
    type_zh: str = ""
    modifies: str = ""
    explanation: str = ""


class MainClause(_Base):
    subject: str = ""
    predicate: str = ""
    object: str = ""
    complement: str = ""
    summary_zh: str = ""


class Syntax(_Base):
    structure_summary: str = ""
    skeleton: str = ""
    main_clause: MainClause = Field(default_factory=MainClause)
    segments: list[SyntaxSegment] = Field(default_factory=list)
    clauses: list[Clause] = Field(default_factory=list)


class GrammarPoint(_Base):
    name: str = ""
    name_zh: str = ""
    source: str = ""
    explanation: str = ""
    why_used_here: str = ""
    simple_example: str = ""
    simple_example_zh: str = ""
    common_mistake: str = ""
    importance: int = Field(default=3, ge=1, le=5)


class Word(_Base):
    surface: str = ""
    lemma: str = ""
    phonetic: str = ""
    pos: str = ""
    pos_zh: str = ""
    meaning_in_context: str = ""
    common_meanings: list[str] = Field(default_factory=list)
    academic_meaning: str = ""
    why_here: str = ""
    collocations: list[str] = Field(default_factory=list)
    difficulty: int = Field(default=3, ge=1, le=5)
    worth_learning: bool = True


class Phrase(_Base):
    text: str = ""
    meaning: str = ""
    explanation: str = ""
    academic_usage: str = ""
    example: str = ""
    example_zh: str = ""
    worth_learning: bool = True


class AcademicExpression(_Base):
    text: str = ""
    meaning: str = ""
    usage: str = ""
    when_to_use: str = ""
    example: str = ""
    example_zh: str = ""


class Reference(_Base):
    expression: str = ""
    refers_to: str = ""
    explanation: str = ""


class Concept(_Base):
    term: str = ""
    translation: str = ""
    simple_explanation: str = ""
    meaning_in_this_paper: str = ""
    background_needed: bool = False


class Misunderstanding(_Base):
    wrong_interpretation: str = ""
    why_wrong: str = ""
    correct_interpretation: str = ""


class WebSource(_Base):
    title: str = ""
    url: str = ""


class WebResearch(_Base):
    used: bool = False
    paper_identified: bool = False
    notes: str = ""
    sources: list[WebSource] = Field(default_factory=list)


class PaperAnalysis(_Base):
    """The complete analysis returned by the AI."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    schema_version: str = SCHEMA_VERSION
    source_text: str = ""
    translation: Translation = Field(default_factory=Translation)
    overview: SentenceOverview = Field(default_factory=SentenceOverview)
    syntax: Syntax = Field(default_factory=Syntax)
    grammar_points: list[GrammarPoint] = Field(default_factory=list)
    words: list[Word] = Field(default_factory=list)
    phrases: list[Phrase] = Field(default_factory=list)
    academic_expressions: list[AcademicExpression] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    concepts: list[Concept] = Field(default_factory=list)
    misunderstandings: list[Misunderstanding] = Field(default_factory=list)
    reading_tips: list[str] = Field(default_factory=list)
    web_research: WebResearch = Field(default_factory=WebResearch)

    @field_validator("schema_version")
    @classmethod
    def _check_version(cls, v: str) -> str:
        # Currently only 1.x is accepted; future upgrades add a compat/migration
        # entry point here.
        if not v:
            return SCHEMA_VERSION
        major = v.split(".", 1)[0]
        if major != "1":
            raise ValueError(f"unsupported schema version: {v} (supported: 1.x)")
        return v

    @field_validator(
        "words", "phrases", "grammar_points", "academic_expressions",
        "references", "concepts", "misunderstandings", "reading_tips",
        mode="before",
    )
    @classmethod
    def _cap_list(cls, v: object) -> object:
        if isinstance(v, list) and len(v) > MAX_ITEMS:
            return v[:MAX_ITEMS]
        return v


# ---------------------------------------------------------------------------
# Request-side models


AnalysisDepth = Literal["quick", "standard", "deep"]

DEPTH_LABELS: dict[AnalysisDepth, str] = {
    "quick": "快速理解",
    "standard": "标准分析",
    "deep": "深度学习",
}


class AnalysisRequest(BaseModel):
    """All input for one analysis; consumed by the PromptCompiler.

    `domain` is a stable English identifier from domain/paper.py DOMAIN_VALUES,
    never a Chinese display label.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    source_text: str
    previous_context: str = ""
    following_context: str = ""
    paper_title: str = ""
    doi_or_url: str = ""
    authors: str = ""
    domain: str = "auto"
    analysis_depth: AnalysisDepth = "standard"
    known_knowledge_profile: str = ""
