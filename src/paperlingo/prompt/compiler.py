"""PromptCompiler：把 AnalysisRequest 编译成可直接粘贴给 Web AI 的完整 Prompt。"""

from __future__ import annotations

from dataclasses import dataclass

from paperlingo.domain.analysis import SCHEMA_VERSION, AnalysisRequest
from paperlingo.prompt.profiles import DEFAULT_PROFILE_ID, get_profile
from paperlingo.prompt.templates import (
    _CONTEXT_NEXT,
    _CONTEXT_PREV,
    _WEB_RESEARCH_NO_INFO,
    _WEB_RESEARCH_WITH_INFO,
    DEFAULT_TEMPLATE_ID,
    DEPTH_INSTRUCTIONS,
    REPAIR_TEMPLATE_ID,
    SCHEMA_DESCRIPTION,
    TEMPLATES,
)

#: 领域 -> AI 角色描述
_DOMAIN_ROLES: dict[str, str] = {
    "自动判断": "论文所属领域的专家（请先根据文本自行判断领域）",
    "计算机科学": "计算机科学领域的专家",
    "人工智能": "人工智能领域的专家",
    "网络": "计算机网络领域的专家",
    "网络安全": "网络安全领域的专家",
    "软件工程": "软件工程领域的专家",
    "系统": "计算机系统领域的专家",
    "密码学": "密码学领域的专家",
    "数据库": "数据库领域的专家",
    "其他": "论文所属领域的专家（请先根据文本自行判断领域）",
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
    """将分析请求编译为最终 Prompt 文本。"""

    def __init__(self, template_id: str = DEFAULT_TEMPLATE_ID) -> None:
        if template_id not in TEMPLATES:
            raise PromptCompileError(f"未知模板: {template_id}")
        self.template = TEMPLATES[template_id]

    # ------------------------------------------------------------------
    def compile(self, request: AnalysisRequest, profile_id: str = DEFAULT_PROFILE_ID) -> CompiledPrompt:
        if not request.source_text.strip():
            raise PromptCompileError("原文不能为空")

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
        # 编译结果不应残留未填充的占位符
        leftover = [p for p in self.template.placeholders if "{" + p + "}" in text]
        if leftover:
            raise PromptCompileError(f"模板存在未填充占位符: {leftover}")

        return CompiledPrompt(
            text=text,
            template_id=self.template.template_id,
            template_version=self.template.version,
            profile_id=profile.profile_id,
        )

    # ------------------------------------------------------------------
    def _build_values(self, req: AnalysisRequest) -> dict[str, str]:
        # 上下文块
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

        # 论文信息块
        info_lines: list[str] = []
        if req.paper_title:
            info_lines.append(f"- 标题: {req.paper_title}")
        if req.doi_or_url:
            info_lines.append(f"- DOI/URL: {req.doi_or_url}")
        if req.authors:
            info_lines.append(f"- 作者: {req.authors}")
        if req.domain and req.domain != "自动判断":
            info_lines.append(f"- 领域: {req.domain}")
        paper_info_lines = "\n".join(info_lines) if info_lines else "（未提供）"

        has_paper_info = bool(req.paper_title or req.doi_or_url or req.authors)
        web_instruction = (
            _WEB_RESEARCH_WITH_INFO if has_paper_info else _WEB_RESEARCH_NO_INFO
        ).strip()

        return {
            "domain_role": _DOMAIN_ROLES.get(req.domain, _DOMAIN_ROLES["自动判断"]),
            "web_research_instruction": web_instruction,
            "source_text": req.source_text,
            "context_block": context_block,
            "paper_info_lines": paper_info_lines,
            "depth_instruction": DEPTH_INSTRUCTIONS[req.analysis_depth].strip(),
            "schema_version": SCHEMA_VERSION,
            "schema_description": SCHEMA_DESCRIPTION.strip(),
        }


def compile_repair_prompt(error: str, raw_response: str, *, excerpt_limit: int = 3000) -> str:
    """解析失败时生成的修复 Prompt。"""
    excerpt = raw_response[:excerpt_limit]
    if len(raw_response) > excerpt_limit:
        excerpt += "\n……（后续内容已省略）"
    return (
        TEMPLATES[REPAIR_TEMPLATE_ID]
        .parts[0]
        .replace("{error}", error.strip() or "未知错误")
        .replace("{raw_response_excerpt}", "你上次的输出（节选）：\n" + excerpt if excerpt else "")
        .replace("{schema_version}", SCHEMA_VERSION)
        .strip()
    )
