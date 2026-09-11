"""AI Response 解析器。

AI Response 属于不可信输入。解析策略：
1. 预处理（去 BOM、零宽字符、智能引号——仅限明显安全的形式转换）；
2. 尝试整体严格解析；
3. 尝试 markdown ```json 围栏；
4. 平衡括号扫描，定位第一个完整 JSON 对象；
5. 全部失败时返回带位置信息的错误。

解析出的 dict 再交给 Pydantic 校验。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from paperlingo.parser.repair import RepairAction, try_repair

#: Input length cap (1MB, so abnormal input cannot stall the app)
MAX_RESPONSE_LENGTH = 1_000_000

_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*\r?\n(.*?)```", re.DOTALL)


@dataclass(frozen=True)
class ParseError:
    message: str
    line: int | None = None
    column: int | None = None
    position: int | None = None
    raw: str = ""

    def describe(self) -> str:
        loc = ""
        if self.line is not None:
            loc = f"（第 {self.line} 行，第 {self.column} 列）"
        return f"{self.message}{loc}"


@dataclass(frozen=True)
class ParseResult:
    ok: bool
    data: dict | None = None
    error: ParseError | None = None
    repairs: list[RepairAction] = field(default_factory=list)
    #: The JSON text that actually participated in parsing (possibly extracted)
    extracted: str = ""


def _preprocess(raw: str) -> tuple[str, list[RepairAction]]:
    """Only safe form normalization: BOM, zero-width characters, full-width spaces, CRLF."""
    repairs: list[RepairAction] = []
    text = raw
    if text.startswith("﻿"):
        text = text.lstrip("﻿")
        repairs.append(RepairAction("remove_bom", "removed BOM"))
    for ch, name in (("​", "零宽空格"), ("‌", "零宽连接符"), ("‍", "零宽连接符"), ("⁠", "单词连接符")):
        if ch in text:
            text = text.replace(ch, "")
            repairs.append(RepairAction("remove_invisible", f"removed {name}"))
    if "　" in text:
        text = text.replace("　", " ")
        repairs.append(RepairAction("fullwidth_space", "full-width space normalized"))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.strip(), repairs


def _json_error_to_parse_error(e: json.JSONDecodeError, source: str) -> ParseError:
    return ParseError(
        message=f"JSON 语法错误: {e.msg}",
        line=e.lineno,
        column=e.colno,
        position=e.pos,
        raw=source,
    )


def _try_loads(text: str) -> tuple[dict | None, ParseError | None]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return None, _json_error_to_parse_error(e, text)
    if not isinstance(data, dict):
        return None, ParseError(message="顶层 JSON 必须是一个对象 {...}", raw=text)
    return data, None


def _extract_fenced(text: str) -> list[str]:
    return [m.group(1).strip() for m in _FENCE_RE.finditer(text)]


def _extract_balanced(text: str) -> list[str]:
    """Scan the text and extract all balanced outer {...} blocks (ignoring braces inside strings)."""
    results: list[str] = []
    depth = 0
    start = -1
    in_string = False
    escape = False
    for i, ch in enumerate(text):
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
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0:
                results.append(text[start : i + 1])
    return results


def parse_response(raw: str) -> ParseResult:
    """Parse the raw AI response into a structured result. Never raises."""
    if not raw or not raw.strip():
        return ParseResult(ok=False, error=ParseError(message="内容为空，请先粘贴 AI 返回结果"))

    if len(raw) > MAX_RESPONSE_LENGTH:
        return ParseResult(
            ok=False,
            error=ParseError(message=f"内容过长（{len(raw)} 字符），上限 {MAX_RESPONSE_LENGTH}"),
        )

    text, repairs = _preprocess(raw)

    def attempt(candidate: str, extra_repairs: list[RepairAction]) -> ParseResult | None:
        data, _err = _try_loads(candidate)
        if data is not None:
            return ParseResult(ok=True, data=data, repairs=repairs + extra_repairs, extracted=candidate)
        # Try bounded repair
        fixed, fix_actions = try_repair(candidate)
        if fixed is not None and fix_actions:
            data2, _err2 = _try_loads(fixed)
            if data2 is not None:
                return ParseResult(
                    ok=True,
                    data=data2,
                    repairs=repairs + extra_repairs + fix_actions,
                    extracted=fixed,
                )
        return None

    # 1. strict parse of the whole text
    r = attempt(text, [])
    if r:
        return r

    candidates: list[str] = []
    # 2. markdown fences
    candidates.extend(_extract_fenced(text))
    # 3. balanced-brace extraction
    candidates.extend(_extract_balanced(text))

    for cand in candidates:
        r = attempt(cand, [RepairAction("extract", "extracted the JSON object from surrounding text")])
        if r:
            return r

    # All attempts failed: report the most useful error
    if candidates:
        _data, err = _try_loads(candidates[0])
        if err:
            return ParseResult(
                ok=False,
                error=ParseError(
                    message=err.message, line=err.line, column=err.column,
                    position=err.position, raw=raw,
                ),
                extracted=candidates[0],
            )
    _data, err = _try_loads(text)
    return ParseResult(
        ok=False,
        error=err or ParseError(message="无法解析为 JSON", raw=raw),
        extracted=text,
    )
