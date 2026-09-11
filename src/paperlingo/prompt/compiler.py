"""PromptCompiler: compiles an AnalysisRequest into a complete prompt ready to
paste into a web AI."""

from __future__ import annotations

import json
from dataclasses import dataclass

from paperlingo.domain.analysis import SCHEMA_VERSION, AnalysisRequest
from paperlingo.prompt.profiles import DEFAULT_PROFILE_ID, get_profile
from paperlingo.prompt.templates import (
    _CONTEXT_NEXT,
    _CONTEXT_PREV,
    _PROFILE_HEADER,
    _WEB_RESEARCH_NO_INFO,
    _WEB_RESEARCH_WITH_INFO,
    DEFAULT_TEMPLATE_ID,
    DEPTH_INSTRUCTIONS,
    REPAIR_TEMPLATE_ID,
    SCHEMA_DESCRIPTION,
    TEMPLATES,
)

#: Domain value -> AI role description (all English; keys are stable identifiers)
_DOMAIN_ROLES: dict[str, str] = {
    "auto": "an expert in the paper's field (determine the field from the text yourself first)",
    "computer_science": "a computer science domain expert",
    "artificial_intelligence": "an artificial intelligence domain expert",
    "networking": "a computer networking domain expert",
    "cybersecurity": "a cybersecurity domain expert",
    "software_engineering": "a software engineering domain expert",
    "systems": "a computer systems domain expert",
    "cryptography": "a cryptography domain expert",
    "databases": "a database systems domain expert",
    "other": "an expert in the paper's field (determine the field from the text yourself first)",
}


@dataclass(frozen=True)
class CompiledPrompt:
    text: str
    template_id: str
    template_version: str
    profile_id: str


class PromptCompileError(ValueError):
    pass


class PromptCompiler:
    """Compiles an analysis request into the final prompt text."""

    def __init__(self, template_id: str = DEFAULT_TEMPLATE_ID) -> None:
        if template_id not in TEMPLATES:
            raise PromptCompileError(f"unknown template: {template_id}")
        self.template = TEMPLATES[template_id]

    # ------------------------------------------------------------------
    def compile(self, request: AnalysisRequest, profile_id: str = DEFAULT_PROFILE_ID) -> CompiledPrompt:
        if not request.source_text.strip():
            raise PromptCompileError("source text must not be empty")

        profile = get_profile(profile_id)
        values = self._build_values(request)

        chunks: list[str] = []
        if profile.preamble:
            chunks.append(profile.preamble.strip())

        for part in self.template.parts:
            rendered = part
            for key, value in values.items():
                rendered = rendered.replace("{" + key + "}", value)
            rendered = rendered.strip()
            if rendered:
                chunks.append(rendered)

        if profile.output_reminder:
            chunks.append(profile.output_reminder.strip())

        text = "\n\n".join(chunks)
        # The compiled result must not leave unfilled placeholders behind.
        leftover = [p for p in self.template.placeholders if "{" + p + "}" in text]
        if leftover:
            raise PromptCompileError(f"template has unfilled placeholders: {leftover}")

        return CompiledPrompt(
            text=text,
            template_id=self.template.template_id,
            template_version=self.template.version,
            profile_id=profile.profile_id,
        )

    # ------------------------------------------------------------------
    def _build_values(self, req: AnalysisRequest) -> dict[str, str]:
        # Context block
        ctx_parts: list[str] = []
        if req.previous_context:
            ctx_parts.append(
                _CONTEXT_PREV.replace("{previous_context}", req.previous_context).strip()
            )
        if req.following_context:
            ctx_parts.append(
                _CONTEXT_NEXT.replace("{following_context}", req.following_context).strip()
            )
        context_block = "\n\n".join(ctx_parts)

        # Paper info block
        info_lines: list[str] = []
        if req.paper_title:
            info_lines.append(f"- Title: {req.paper_title}")
        if req.doi_or_url:
            info_lines.append(f"- DOI/URL: {req.doi_or_url}")
        if req.authors:
            info_lines.append(f"- Authors: {req.authors}")
        if req.domain and req.domain != "auto":
            info_lines.append(f"- Research field: {req.domain}")
        paper_info_lines = "\n".join(info_lines) if info_lines else "(not provided)"

        has_paper_info = bool(req.paper_title or req.doi_or_url or req.authors)
        web_instruction = (
            _WEB_RESEARCH_WITH_INFO if has_paper_info else _WEB_RESEARCH_NO_INFO
        ).strip()

        # Learner profile: only included when enough weakness data was collected.
        # Always generated in English, e.g. "Weak learning categories: vocabulary=4, grammar=2."
        profile_text = req.known_knowledge_profile.strip()
        knowledge_profile_block = (
            f"{_PROFILE_HEADER}\n{profile_text}" if profile_text else ""
        )

        return {
            "domain_role": _DOMAIN_ROLES.get(req.domain, _DOMAIN_ROLES["auto"]),
            "web_research_instruction": web_instruction,
            "source_text": req.source_text,
            "context_block": context_block,
            "paper_info_lines": paper_info_lines,
            "knowledge_profile_block": knowledge_profile_block,
            "depth_instruction": DEPTH_INSTRUCTIONS[req.analysis_depth].strip(),
            "schema_version": SCHEMA_VERSION,
            "schema_description": SCHEMA_DESCRIPTION.strip(),
        }


def compile_repair_prompt(error: str, raw_response: str, *, excerpt_limit: int = 3000) -> str:
    """Build the repair prompt for a failed parse.

    The raw AI response may contain Chinese; to keep the repair instructions
    English-only, the excerpt is embedded as an ASCII-safe JSON-escaped string
    (json.dumps with ensure_ascii=True). This preserves the semantic content of
    the original response exactly while keeping the prompt language contract.
    """
    excerpt = raw_response[:excerpt_limit]
    if len(raw_response) > excerpt_limit:
        excerpt += "... (the rest was truncated)"
    excerpt_block = ""
    if excerpt:
        escaped = json.dumps(excerpt, ensure_ascii=True)
        excerpt_block = "Your previous output (excerpt, JSON-escaped):\n" + escaped
    return (
        TEMPLATES[REPAIR_TEMPLATE_ID]
        .parts[0]
        .replace("{error}", json.dumps(error.strip() or "unknown error", ensure_ascii=True)[1:-1])
        .replace("{raw_response_excerpt}", excerpt_block)
        .replace("{schema_version}", SCHEMA_VERSION)
        .strip()
    )
