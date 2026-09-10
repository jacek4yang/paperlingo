"""有限度的 JSON 修复。

只允许"形式级"修复，绝不改变语义：
- 智能引号 -> 直引号
- 去除对象/数组尾部的多余逗号
- 未闭合的括号/字符串尝试收尾

不允许：猜测字段名、补全缺失内容、修改字符串值。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SMART_TO_STRAIGHT = {
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
}

#: 尾部逗号：{"a":1,} 或 [1,2,]
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
    """如果 JSON 被截断（括号/字符串未闭合），尝试补一个合法结尾。"""
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
    """尝试修复，返回 (修复后文本, 修复动作列表)。无法修复返回 (None, [])。"""
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
