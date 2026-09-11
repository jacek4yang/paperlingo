"""PromptCompiler tests, including the prompt language contract.

The language contract is non-negotiable (see AGENTS.md): compiled prompts for
English input must contain no CJK characters and must explicitly request
Simplified Chinese output. Do not weaken these tests to make failures disappear.
"""

from __future__ import annotations

import pytest

from paperlingo.domain.analysis import SCHEMA_VERSION, AnalysisRequest
from paperlingo.prompt.compiler import PromptCompileError, PromptCompiler, compile_repair_prompt
from paperlingo.prompt.profiles import list_profiles
from paperlingo.prompt.templates import DEFAULT_TEMPLATE_ID, SCHEMA_DESCRIPTION, TEMPLATES

# CJK ranges: U+3400-U+4DBF (ext A), U+4E00-U+9FFF (CJK unified),
# U+F900-U+FAFF (compatibility ideographs), plus CJK punctuation.
_CJK_RANGES = (
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0x3000, 0x303F),
    (0xFF00, 0xFFEF),
)


def _contains_cjk(text: str) -> bool:
    for ch in text:
        cp = ord(ch)
        if any(lo <= cp <= hi for lo, hi in _CJK_RANGES):
            return True
    return False


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


def test_no_cjk_in_compiled_prompts() -> None:
    """English-only input must produce an English-only prompt, for every profile
    and every analysis depth."""
    req = _req(
        previous_context="Some previous context in English.",
        following_context="Some following context in English.",
        paper_title="A Survey of X",
        doi_or_url="10.1000/xyz",
        authors="J. Doe",
        domain="computer_science",
    )
    for depth in ("quick", "standard", "deep"):
        for profile in list_profiles():
            compiled = PromptCompiler().compile(req, profile.profile_id)
            assert not _contains_cjk(compiled.text), (
                f"CJK character found in prompt (depth={depth}, profile={profile.profile_id})"
            )


def test_prompt_requests_simplified_chinese_output() -> None:
    compiled = PromptCompiler().compile(_req())
    assert "Simplified Chinese" in compiled.text
    assert "native Chinese speaker" in compiled.text


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
    assert "confirm the original paper" in compiled.text
    assert "A Survey of X" in compiled.text
    assert "10.1000/xyz" in compiled.text


def test_no_paper_info_uses_no_search_instruction() -> None:
    compiled = PromptCompiler().compile(_req())
    assert "did not provide enough information to locate the paper" in compiled.text


def test_context_included() -> None:
    compiled = PromptCompiler().compile(
        _req(previous_context="PREV_CTX_UNIQUE", following_context="NEXT_CTX_UNIQUE")
    )
    assert "PREV_CTX_UNIQUE" in compiled.text
    assert "NEXT_CTX_UNIQUE" in compiled.text


def test_knowledge_profile_included_when_present() -> None:
    compiled = PromptCompiler().compile(
        _req(known_knowledge_profile="Weak learning categories: vocabulary=4, grammar=2.")
    )
    assert "Learner profile" in compiled.text
    assert "Weak learning categories: vocabulary=4, grammar=2." in compiled.text


def test_knowledge_profile_omitted_when_empty() -> None:
    compiled = PromptCompiler().compile(_req())
    assert "Learner profile" not in compiled.text


def test_depth_changes_instruction() -> None:
    quick = PromptCompiler().compile(_req(analysis_depth="quick")).text
    deep = PromptCompiler().compile(_req(analysis_depth="deep")).text
    assert "quick understanding" in quick
    assert "deep learning" in deep
    assert quick != deep


def test_profiles_share_core_but_differ_in_reminder() -> None:
    texts = {p.profile_id: PromptCompiler().compile(_req(), p.profile_id).text for p in list_profiles()}
    assert "academic English expert" in texts["generic"]
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
    text = compile_repair_prompt('JSON syntax error: Expecting value', "{oops")
    assert "JSON syntax error" in text
    assert SCHEMA_VERSION in text
    assert "{oops" in text


def test_repair_prompt_language_contract() -> None:
    """The repair prompt must stay English-only even when the raw AI response
    contains Chinese: the payload is embedded ASCII-escaped."""
    raw = ' natural: "这里是一个中文示例翻译" '
    text = compile_repair_prompt("JSON 语法错误: Expecting value", raw)
    assert not _contains_cjk(text), "CJK leaked into the repair prompt"
    # The Chinese payload must survive, semantically intact, as \uXXXX escapes.
    assert "\\u4e2d\\u6587" in text  # 中文
    assert "Repair JSON syntax only" in text
    assert "Do not change any semantic content" in text
    assert "Return only valid JSON" in text
