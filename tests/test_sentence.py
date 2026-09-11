"""Interactive sentence span mapping."""

from paperlingo.ui.widgets.sentence import find_span


def test_exact_match() -> None:
    src = "We address this gap through a curated corpus."
    assert find_span(src, "address this gap") == (3, 19)


def test_case_insensitive() -> None:
    src = "We Address this gap."
    span = find_span(src, "address this gap")
    assert span is not None
    assert src[span[0]:span[1]].lower() == "address this gap"


def test_no_false_match() -> None:
    src = "We address this gap."
    assert find_span(src, "completely absent phrase") is None


def test_empty_needle() -> None:
    assert find_span("hello", "   ") is None
