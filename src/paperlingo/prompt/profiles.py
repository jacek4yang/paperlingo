"""Prompt profiles: per-web-AI differences.

Architecturally, each model may override parts of the prompt instead of the UI
sprinkling `if model == "grok"` everywhere. In v1 all profiles share the template;
they differ only in the system preamble / output reminder. All instruction text is
English; `display_name` is a UI-facing label and may be Simplified Chinese.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptProfile:
    """Prompt configuration for one web AI."""

    profile_id: str
    display_name: str
    #: Extra instruction prepended to the prompt (may be empty)
    preamble: str = ""
    #: Reminder appended after the output protocol (may be empty)
    output_reminder: str = ""
    #: Whether this AI generally supports web search (only used to inform the user)
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
        output_reminder="\nReminder: output the JSON object itself directly; do not use a code block.",
    ),
    PromptProfile(
        profile_id="claude",
        display_name="Claude",
        preamble="",
        output_reminder="\nReminder: output only the JSON object, with no preamble or closing remarks.",
    ),
    PromptProfile(
        profile_id="grok",
        display_name="Grok",
        preamble="",
        output_reminder="\nReminder: the final reply must contain only the JSON object and nothing else.",
    ),
    PromptProfile(
        profile_id="gemini",
        display_name="Gemini",
        preamble="",
        output_reminder="\nReminder: output a single JSON object; do not use a Markdown code block.",
    ),
)

_BY_ID: dict[str, PromptProfile] = {p.profile_id: p for p in _PROFILES}

DEFAULT_PROFILE_ID = "generic"


def list_profiles() -> list[PromptProfile]:
    return list(_PROFILES)


def get_profile(profile_id: str) -> PromptProfile:
    return _BY_ID.get(profile_id, _BY_ID[DEFAULT_PROFILE_ID])
