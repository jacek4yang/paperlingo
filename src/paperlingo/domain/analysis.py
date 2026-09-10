"""AI 返回结果的结构化 Schema（Pydantic v2）。

设计原则：
- AI 只返回结构化 JSON，绝不返回 HTML / CSS / Markdown / 可执行代码。
- 所有字段对"现实中 Web AI 能稳定生成的复杂度"友好：几乎一切可缺省，
  缺省时为空列表 / 空字符串 / null，禁止 AI 为填满 Schema 编造内容。
- schema 有 version（SCHEMA_VERSION），未来升级时做迁移。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: 当前 schema 版本。Prompt 中要求 AI 原样带回。
SCHEMA_VERSION = "1.0"

#: 单个文本字段的最大长度（防御异常输出）
MAX_TEXT_LENGTH = 4000
#: 列表类字段的最大条目数
MAX_ITEMS = 100


class _Base(BaseModel):
    """公共基类：禁止多余字段报错（宽松），但截断超长字符串。"""

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
    """原句中的一个片段及其语法角色。text 必须能在原句中找到（用于交互高亮）。"""

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
    """AI 返回的完整分析结果。"""

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
        # 目前只接受 1.x；未来升级时在这里做兼容/迁移入口
        if not v:
            return SCHEMA_VERSION
        major = v.split(".", 1)[0]
        if major != "1":
            raise ValueError(f"不支持的 schema 版本: {v}（当前支持 1.x）")
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
# 请求侧模型


AnalysisDepth = Literal["quick", "standard", "deep"]

DEPTH_LABELS: dict[AnalysisDepth, str] = {
    "quick": "快速理解",
    "standard": "标准分析",
    "deep": "深度学习",
}


class AnalysisRequest(BaseModel):
    """一次分析的全部输入，由 PromptCompiler 消费。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    source_text: str
    previous_context: str = ""
    following_context: str = ""
    paper_title: str = ""
    doi_or_url: str = ""
    authors: str = ""
    domain: str = "自动判断"
    analysis_depth: AnalysisDepth = "standard"
    known_knowledge_profile: str = ""
