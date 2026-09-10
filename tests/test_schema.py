"""Pydantic Schema 校验。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from paperlingo.domain.analysis import SCHEMA_VERSION, AnalysisRequest, PaperAnalysis

FIXTURES = Path(__file__).parent / "fixtures"


def test_minimal_analysis_ok() -> None:
    a = PaperAnalysis()
    assert a.schema_version == SCHEMA_VERSION
    assert a.words == []
    assert a.translation.natural == ""


def test_clean_fixture_validates() -> None:
    data = json.loads((FIXTURES / "clean.json").read_text(encoding="utf-8"))
    a = PaperAnalysis.model_validate(data)
    assert a.source_text.startswith("In this survey")
    assert a.translation.natural
    assert a.overview.difficulty == 4
    assert any(w.lemma == "curate" for w in a.words)
    assert a.web_research.used is False


def test_missing_optional_fields_ok() -> None:
    data = json.loads((FIXTURES / "missing_optional_fields.json").read_text(encoding="utf-8"))
    a = PaperAnalysis.model_validate(data)
    assert a.translation.natural == "我们提出一种简单方法。"
    assert a.words == []
    assert a.overview.difficulty == 3  # 默认


def test_unsupported_schema_version() -> None:
    with pytest.raises(ValidationError):
        PaperAnalysis.model_validate({"schema_version": "2.0", "source_text": "x"})


def test_empty_schema_version_defaults() -> None:
    a = PaperAnalysis.model_validate({"schema_version": "", "source_text": "hi"})
    assert a.schema_version == SCHEMA_VERSION


def test_extra_fields_ignored() -> None:
    a = PaperAnalysis.model_validate({"schema_version": "1.0", "unknown_field": 123})
    assert not hasattr(a, "unknown_field")


def test_list_capped_at_max() -> None:
    words = [{"surface": f"w{i}", "lemma": f"w{i}"} for i in range(150)]
    a = PaperAnalysis.model_validate({"schema_version": "1.0", "words": words})
    assert len(a.words) == 100


def test_difficulty_out_of_range() -> None:
    with pytest.raises(ValidationError):
        PaperAnalysis.model_validate({"overview": {"difficulty": 9}})


def test_analysis_request_requires_source() -> None:
    with pytest.raises(ValidationError):
        AnalysisRequest()  # type: ignore[call-arg]


def test_analysis_request_defaults() -> None:
    r = AnalysisRequest(source_text="Hello")
    assert r.analysis_depth == "standard"
    assert r.domain == "自动判断"
