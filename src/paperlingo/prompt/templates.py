"""Prompt 模板系统。

模板不是写死的一大段字符串：每个模板有版本号，由模板部分（part）组合而成，
测试会校验模板的占位符与编译结果。未来升级分析协议时新增模板版本即可。
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: 当前默认分析模板版本
DEFAULT_TEMPLATE_ID = "paper_analysis_v1"

#: 修复 Prompt 模板版本
REPAIR_TEMPLATE_ID = "repair_v1"


@dataclass(frozen=True)
class PromptTemplate:
    template_id: str
    version: str
    #: 有序的部分列表；每部分是带 {placeholder} 的文本
    parts: tuple[str, ...]
    description: str = ""
    #: 该模板允许出现的全部占位符（用于编译时校验）
    placeholders: frozenset[str] = field(default_factory=frozenset)


# ---------------------------------------------------------------------------
# paper_analysis_v1 的各组成部分
# ---------------------------------------------------------------------------

_ROLE = """\
你同时是：
1. 学术英语专家
2. 语言学专家
3. 科研论文阅读专家
4. {domain_role}

你的服务对象是：中文母语、正在学习科研英语的计算机专业学生。
所有解释使用清晰、自然的中文；不要用语言学术语堆砌，要让学生真正理解。
"""

_WEB_RESEARCH = """\
【论文定位与联网检索】
{web_research_instruction}
"""

_WEB_RESEARCH_WITH_INFO = """\
用户提供了论文信息（标题/DOI/URL/作者）。如果你的环境支持联网搜索：
1. 先搜索并确认原论文；
2. 阅读必要的上下文，理解作者在论文中的真实语义；
3. 优先参考论文自身及可靠学术来源；
4. 不得因为普通字典义而错误翻译专业术语；
5. 如果搜不到，在 web_research.notes 中明确说明，不得伪造来源；
6. 联网结果只用于提高理解质量，绝不得覆盖或修改用户提供的原文。
在 web_research 字段中如实填写 used / paper_identified / notes / sources。
如果你不能联网，将 web_research.used 设为 false 并直接基于所给文本分析。
"""

_WEB_RESEARCH_NO_INFO = """\
用户没有提供足以定位论文的信息。如果你认为联网搜索论文原文能显著提高理解质量，
且你的环境支持联网，可以尝试；否则将 web_research.used 设为 false，
直接基于所给文本分析。不得伪造来源。
"""

_CONTEXT = """\
【待分析原文】
（这是唯一需要分析的对象，逐字引用，不要修改）
<source_text>
{source_text}
</source_text>

{context_block}\
"""

_CONTEXT_PREV = """\
【上文（仅供理解，不需要分析）】
<previous_context>
{previous_context}
</previous_context>
"""

_CONTEXT_NEXT = """\
【下文（仅供理解，不需要分析）】
<following_context>
{following_context}
</following_context>
"""

_PAPER_INFO = """\
【论文信息】
{paper_info_lines}
"""

_PROFILE = """\
【学习者画像（仅供参考，不得因此跳过核心结构分析）】
{knowledge_profile}
"""

_TASK = """\
【任务】
按下面的优先级分析 <source_text> 中的英文：
1. 精准理解作者到底想表达什么
2. 准确翻译（区分直译与自然翻译，不要翻译腔）
3. 拆解长难句结构（主谓宾、从句、修饰关系）
4. 讲清中文母语者容易卡住的语法点
5. 解释单词在"本语境"中的含义（而不是词典第一释义）
6. 提取值得学习的固定搭配与学术写作表达
7. 分析指代关系（it/this/these/they/which/that/such/the former/the latter 等）
8. 解释专业概念（区分"英语不会"与"英语认识但专业知识不会"）
9. 指出典型的中式英语误读

不要对 the / a / is / of / and 这类基础词逐词浪费篇幅，
除非它在特殊语法结构中发挥关键作用。

所有教学解释优先回答：
- 为什么？
- 这里到底是什么结构？
- 阅读时应该从哪里开始读？
- 哪个词修饰哪个词？
- 为什么不能按字面顺序理解？
- 下次看到类似句子怎么快速识别？
不要只给术语标签。例如不要只写"这是非限制性定语从句"，
还要写"阅读时可以先把它括起来，先读完主句再回来补充这部分信息"。
"""

_DEPTH_QUICK = """\
【分析深度：快速理解】
用户只想快速看懂这句话。要求：
- translation.natural / core_meaning 必须高质量；
- overview 必填；
- syntax 只给 structure_summary、skeleton 和最关键的 3~8 个 segments；
- grammar_points 最多 1 条（只讲最卡人的）；
- words 最多 3 个（只挑真正影响理解的）；
- phrases / academic_expressions 各最多 2 条；
- references 只填影响理解的指代；
- concepts 最多 2 个；misunderstandings 最多 1 条；
- reading_tips 给 1 条即可。
"""

_DEPTH_STANDARD = """\
【分析深度：标准分析】
给出完整而克制的分析：
- 所有顶层字段都要认真填写，但不为填满而编造；
- words 控制在 8 个以内，只挑值得学的；
- grammar_points 控制在 4 条以内；
- phrases / academic_expressions 各不超过 4 条；
- concepts 不超过 4 个；misunderstandings 不超过 3 条。
"""

_DEPTH_DEEP = """\
【分析深度：深度学习】
用户希望把这句话彻底吃透。在标准分析基础上：
- syntax 的 segments 要覆盖句子的所有关键成分，clauses 完整；
- 每个 grammar_point 都要写清 why_used_here 与 common_mistake；
- words / phrases 可以更丰富，但仍不收基础词；
- reading_tips 给出可迁移到其它论文的阅读方法；
- 如有必要，在 misunderstandings 中预判中国学生最典型的误读。
"""

_OUTPUT = """\
【输出协议（严格遵守）】
1. 最终只输出一个 JSON 对象，不要输出任何 Markdown 标题、解释或注释；
2. 不要把 JSON 包在 ```json 代码块里，直接输出 JSON 本身；
3. JSON 中的字符串如含换行必须正确转义；
4. schema_version 必须原样填写 "{schema_version}"；
5. 无法判断的字段使用 null 或 []，禁止为了填满 Schema 编造内容；
6. 所有中文解释用简体中文；source_text、segments.text、clauses.text、
   words.surface、phrases.text、references.expression 必须逐字来自原文，
   保证能在原文中精确找到（区分大小写）；
7. 不要输出 HTML / CSS / 代码，只输出纯文本内容。

JSON 结构如下（字段名必须完全一致）：
{schema_description}
"""

#: 给 AI 看的 schema 描述（人工维护，与 domain/analysis.py 保持一致，
#: 由测试校验字段名同步）
SCHEMA_DESCRIPTION = """\
{
  "schema_version": "1.0",
  "source_text": "逐字复制的原文",
  "translation": {
    "natural": "符合中文表达习惯的准确翻译（最重要）",
    "literal": "尽量保持英文结构的直译",
    "core_meaning": "作者到底想表达什么（1-2 句）",
    "translation_notes": ["关键翻译决策的理由"]
  },
  "overview": {
    "difficulty": 1-5 的整数,
    "difficulty_reason": "难度原因",
    "sentence_type": "句型概述，如：并列复合句",
    "one_sentence_explanation": "一句话讲清这个句子在干什么",
    "reading_strategy": "读这类句子的策略"
  },
  "syntax": {
    "structure_summary": "如：主句 + 定语从句 + 方式状语",
    "skeleton": "去掉修饰后的句子主干（英文）",
    "main_clause": {"subject": "", "predicate": "", "object": "", "complement": "", "summary_zh": "主干的中文概述"},
    "segments": [{"text": "原文片段", "role": "subject 等英文角色", "role_zh": "主语等中文", "explanation": "该片段的作用与含义"}],
    "clauses": [{"text": "从句原文", "type": "relative_clause 等", "type_zh": "定语从句等", "modifies": "修饰对象", "explanation": "解释"}]
  },
  "grammar_points": [{
    "name": "allow + object + to do", "name_zh": "allow + 宾语 + 不定式",
    "source": "原文中的出处片段",
    "explanation": "结构讲解（要讲到学生真正懂，不要只贴标签）",
    "why_used_here": "作者为什么在这里这么用",
    "simple_example": "一个简单的英文例句", "simple_example_zh": "例句中文",
    "common_mistake": "中国学生最容易犯的错误理解",
    "importance": 1-5 的整数
  }],
  "words": [{
    "surface": "原文中的形态", "lemma": "原形/词元", "phonetic": "音标，不确定留空",
    "pos": "adjective 等", "pos_zh": "形容词等",
    "meaning_in_context": "本句中的含义（最重要）",
    "common_meanings": ["常见含义"], "academic_meaning": "学术语境含义",
    "why_here": "为什么这里要这么理解",
    "collocations": ["常见搭配"], "difficulty": 1-5, "worth_learning": true
  }],
  "phrases": [{
    "text": "短语原文", "meaning": "中文含义", "explanation": "解释",
    "academic_usage": "学术写作中的用法", "example": "例句", "example_zh": "例句中文",
    "worth_learning": true
  }],
  "academic_expressions": [{
    "text": "论文写作常用表达", "meaning": "中文含义",
    "usage": "用法说明", "when_to_use": "什么时候可以用在自己的写作里",
    "example": "例句", "example_zh": "例句中文"
  }],
  "references": [{"expression": "they", "refers_to": "defenses and evaluations", "explanation": "解释"}],
  "concepts": [{
    "term": "prompt injection", "translation": "提示词注入",
    "simple_explanation": "给非专业读者的通俗解释",
    "meaning_in_this_paper": "在本文中的具体含义",
    "background_needed": false
  }],
  "misunderstandings": [{
    "wrong_interpretation": "典型错误理解", "why_wrong": "为什么错",
    "correct_interpretation": "正确理解"
  }],
  "reading_tips": ["可迁移的阅读建议"],
  "web_research": {
    "used": false, "paper_identified": false, "notes": "",
    "sources": [{"title": "", "url": ""}]
  }
}
"""

#: 修复 Prompt：解析失败时让用户拿回去找 AI 修复
REPAIR_TEMPLATE = """\
你上次给我的分析结果无法被程序解析为合法 JSON。

解析错误信息：
{error}

{raw_response_excerpt}

请重新输出：只输出一个完整、合法的 JSON 对象，符合之前给你的 Schema
（schema_version = "{schema_version}"）。
不要输出任何 Markdown、解释或代码块标记，直接输出 JSON 本身。
"""

# ---------------------------------------------------------------------------
# 模板注册表
# ---------------------------------------------------------------------------

TEMPLATES: dict[str, PromptTemplate] = {
    DEFAULT_TEMPLATE_ID: PromptTemplate(
        template_id=DEFAULT_TEMPLATE_ID,
        version="1.0.0",
        description="论文句子/段落深度分析（v1 协议）",
        parts=(
            _ROLE,
            _WEB_RESEARCH,
            _CONTEXT,
            _PAPER_INFO,
            _TASK,
            "{depth_instruction}",
            _OUTPUT,
        ),
        placeholders=frozenset(
            {
                "domain_role",
                "web_research_instruction",
                "source_text",
                "context_block",
                "paper_info_lines",
                "depth_instruction",
                "schema_version",
                "schema_description",
            }
        ),
    ),
    REPAIR_TEMPLATE_ID: PromptTemplate(
        template_id=REPAIR_TEMPLATE_ID,
        version="1.0.0",
        description="AI Response 解析失败时的修复 Prompt",
        parts=(REPAIR_TEMPLATE,),
        placeholders=frozenset({"error", "raw_response_excerpt", "schema_version"}),
    ),
}

DEPTH_INSTRUCTIONS: dict[str, str] = {
    "quick": _DEPTH_QUICK,
    "standard": _DEPTH_STANDARD,
    "deep": _DEPTH_DEEP,
}

__all__ = [
    "DEFAULT_TEMPLATE_ID",
    "DEPTH_INSTRUCTIONS",
    "REPAIR_TEMPLATE_ID",
    "SCHEMA_DESCRIPTION",
    "TEMPLATES",
    "_CONTEXT_NEXT",
    "_CONTEXT_PREV",
    "_WEB_RESEARCH_NO_INFO",
    "_WEB_RESEARCH_WITH_INFO",
    "PromptTemplate",
]
