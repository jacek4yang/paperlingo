"""Prompt Profile：针对不同 Web AI 的差异层。

架构上允许每个模型覆盖部分 Prompt，而不是在 UI 里写 `if model == "grok"`。
v1 中各 Profile 大体共享模板，只在 system preamble / 输出提醒上做微调。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptProfile:
    """一个 Web AI 的提示词配置。"""

    profile_id: str
    display_name: str
    #: 追加在 Prompt 最前面的补充说明（可为空）
    preamble: str = ""
    #: 追加在输出协议之后的提醒（可为空）
    output_reminder: str = ""
    #: 该 AI 是否一般支持联网搜索（仅用于提示用户）
    usually_web_capable: bool = True


_PROFILES: tuple[PromptProfile, ...] = (
    PromptProfile(
        profile_id="generic",
        display_name="通用 Web AI",
        preamble="",
        output_reminder="",
    ),
    PromptProfile(
        profile_id="chatgpt",
        display_name="ChatGPT",
        preamble="",
        output_reminder="\n提醒：直接输出 JSON 对象本身，不要使用代码块。",
    ),
    PromptProfile(
        profile_id="claude",
        display_name="Claude",
        preamble="",
        output_reminder="\n提醒：只输出 JSON 对象，不要附带任何前言或结语。",
    ),
    PromptProfile(
        profile_id="grok",
        display_name="Grok",
        preamble="",
        output_reminder="\n提醒：最终回复只包含 JSON 对象，不含其它任何文字。",
    ),
    PromptProfile(
        profile_id="gemini",
        display_name="Gemini",
        preamble="",
        output_reminder="\n提醒：只输出一个 JSON 对象，不要使用 Markdown 代码块。",
    ),
)

_BY_ID: dict[str, PromptProfile] = {p.profile_id: p for p in _PROFILES}

DEFAULT_PROFILE_ID = "generic"


def list_profiles() -> list[PromptProfile]:
    return list(_PROFILES)


def get_profile(profile_id: str) -> PromptProfile:
    return _BY_ID.get(profile_id, _BY_ID[DEFAULT_PROFILE_ID])
