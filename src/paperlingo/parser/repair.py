"""Bounded JSON repair.

Only form-level repairs are allowed; semantics are never changed:
- smart quotes -> straight quotes
- remove trailing commas in objects/arrays
- attempt to close unterminated brackets/strings

Not allowed: guessing field names, completing missing content, or editing
string values.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SMART_TO_STRAIGHT = {
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
}

#: Trailing comma: {"a":1,} or [1,2,]
_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")


@dataclass(frozen=True)
class RepairAction:
    kind: str
    description: str


def _fix_smart_quotes(text: str) -> tuple[str, bool]:
    changed = False
    for k, v in _SMART_TO_STRAIGHT.items():
        if k in text:
            text = text.replace(k, v)
            changed = True
    return text, changed


def _fix_trailing_commas(text: str) -> tuple[str, bool]:
    new = _TRAILING_COMMA_RE.sub(r"\1", text)
    return new, new != text


def _close_unbalanced(text: str) -> tuple[str, bool]:
    """If the JSON is truncated (unterminated brackets/strings), append a valid ending."""
    in_string = False
    escape = False
    stack: list[str] = []
    for ch in text:
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]" and stack:
            stack.pop()
    if not in_string and not stack:
        return text, False
    fixed = text
    if in_string:
        fixed += '"'
    for ch in reversed(stack):
        fixed += "}" if ch == "{" else "]"
    return fixed, True


def try_repair(text: str) -> tuple[str | None, list[RepairAction]]:
    """Attempt repair; returns (fixed text, repair actions). (None, []) when unrepairable."""
    actions: list[RepairAction] = []
    fixed = text

    fixed, changed = _fix_smart_quotes(fixed)
    if changed:
        actions.append(RepairAction("smart_quotes", "智能引号替换为直引号"))

    fixed, changed = _fix_trailing_commas(fixed)
    if changed:
        actions.append(RepairAction("trailing_comma", "移除对象/数组尾部多余逗号"))

    fixed, changed = _close_unbalanced(fixed)
    if changed:
        actions.append(RepairAction("close_brackets", "补齐未闭合的括号/引号（输出可能被截断）"))

    if not actions:
        return None, []
    return fixed, actions
