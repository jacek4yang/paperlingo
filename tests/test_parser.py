"""Response parser tests."""

from __future__ import annotations

from pathlib import Path

from paperlingo.domain.analysis import PaperAnalysis
from paperlingo.parser.response_parser import parse_response

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_clean_json() -> None:
    r = parse_response(_load("clean.json"))
    assert r.ok
    assert r.data is not None
    a = PaperAnalysis.model_validate(r.data)
    assert "curated" in a.source_text


def test_markdown_fenced() -> None:
    r = parse_response(_load("markdown_fenced.txt"))
    assert r.ok
    assert r.data is not None
    assert r.data["schema_version"] == "1.0"
    assert any(act.kind == "extract" for act in r.repairs)


def test_leading_text() -> None:
    r = parse_response(_load("leading_text.txt"))
    assert r.ok
    assert r.data is not None
    assert r.data["source_text"].startswith("Existing studies")


def test_invalid_json_reports_error() -> None:
    r = parse_response(_load("invalid.json"))
    assert not r.ok
    assert r.error is not None
    assert "JSON" in r.error.message or "无法解析" in r.error.message
    assert r.error.line is not None or r.error.message


def test_empty_input() -> None:
    r = parse_response("   ")
    assert not r.ok
    assert "空" in r.error.message  # type: ignore[union-attr]


def test_bom_stripped() -> None:
    payload = _load("missing_optional_fields.json")
    r = parse_response("﻿" + payload)
    assert r.ok
    assert r.data is not None
    assert r.data["source_text"] == "We propose a simple method."


def test_trailing_comma_repaired() -> None:
    text = '{"schema_version": "1.0", "source_text": "hi",}'
    r = parse_response(text)
    assert r.ok
    assert r.data is not None
    assert any(act.kind == "trailing_comma" for act in r.repairs)


def test_smart_quotes_repaired() -> None:
    text = '{“schema_version”: “1.0”, “source_text”: “hi”}'
    r = parse_response(text)
    assert r.ok
    assert r.data is not None


def test_array_top_level_rejected() -> None:
    r = parse_response("[1, 2, 3]")
    assert not r.ok
    assert "对象" in r.error.message  # type: ignore[union-attr]


def test_missing_optional_fields_parses_and_validates() -> None:
    r = parse_response(_load("missing_optional_fields.json"))
    assert r.ok
    a = PaperAnalysis.model_validate(r.data)
    assert a.translation.natural
    assert a.words == []
