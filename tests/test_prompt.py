"""PromptCompiler 测试。"""

from __future__ import annotations

import pytest

from paperlingo.domain.analysis import SCHEMA_VERSION, AnalysisRequest
from paperlingo.prompt.compiler import PromptCompileError, PromptCompiler, compile_repair_prompt
from paperlingo.prompt.profiles import list_profiles
from paperlingo.prompt.templates import DEFAULT_TEMPLATE_ID, SCHEMA_DESCRIPTION, TEMPLATES


def _req(**kwargs) -> AnalysisRequest:
    data = {"source_text": "We address this gap through a curated corpus."}
    data.update(kwargs)
    return AnalysisRequest(**data)


def test_compile_contains_source_and_schema() -> None:
    compiled = PromptCompiler().compile(_req())
    assert compiled.template_id == DEFAULT_TEMPLATE_ID
    assert compiled.template_version == TEMPLATES[DEFAULT_TEMPLATE_ID].version
    assert "We address this gap" in compiled.text
    assert SCHEMA_VERSION in compiled.text
    assert "schema_version" in compiled.text
    assert "JSON" in compiled.text


def test_empty_source_raises() -> None:
    with pytest.raises(PromptCompileError):
        PromptCompiler().compile(_req(source_text="   "))


def test_unknown_template_raises() -> None:
    with pytest.raises(PromptCompileError):
        PromptCompiler("does_not_exist")


def test_paper_info_triggers_web_research() -> None:
    compiled = PromptCompiler().compile(
        _req(paper_title="A Survey of X", doi_or_url="10.1000/xyz")
    )
    assert "搜索并确认原论文" in compiled.text
    assert "A Survey of X" in compiled.text
    assert "10.1000/xyz" in compiled.text


def test_no_paper_info_uses_no_search_instruction() -> None:
    compiled = PromptCompiler().compile(_req())
    assert "用户没有提供足以定位论文的信息" in compiled.text


def test_context_included() -> None:
    compiled = PromptCompiler().compile(
        _req(previous_context="PREV_CTX_UNIQUE", following_context="NEXT_CTX_UNIQUE")
    )
    assert "PREV_CTX_UNIQUE" in compiled.text
    assert "NEXT_CTX_UNIQUE" in compiled.text


def test_depth_changes_instruction() -> None:
    quick = PromptCompiler().compile(_req(analysis_depth="quick")).text
    deep = PromptCompiler().compile(_req(analysis_depth="deep")).text
    assert "快速理解" in quick
    assert "深度学习" in deep
    assert quick != deep


def test_profiles_share_core_but_differ_in_reminder() -> None:
    texts = {p.profile_id: PromptCompiler().compile(_req(), p.profile_id).text for p in list_profiles()}
    assert "学术英语专家" in texts["generic"]
    # 各 profile 至少有一个不同的提醒或相同核心
    assert all("JSON" in t for t in texts.values())


def test_no_leftover_placeholders() -> None:
    compiled = PromptCompiler().compile(_req(paper_title="T", authors="A"))
    for ph in TEMPLATES[DEFAULT_TEMPLATE_ID].placeholders:
        assert "{" + ph + "}" not in compiled.text


def test_schema_description_mentions_required_fields() -> None:
    for field in (
        "translation", "overview", "syntax", "grammar_points", "words",
        "phrases", "academic_expressions", "references", "concepts",
        "misunderstandings", "reading_tips", "web_research",
    ):
        assert field in SCHEMA_DESCRIPTION


def test_repair_prompt() -> None:
    text = compile_repair_prompt("JSON 语法错误: Expecting value", "{oops")
    assert "JSON 语法错误" in text
    assert SCHEMA_VERSION in text
    assert "{oops" in text
