"""Centralized Simplified Chinese UI strings for the main workflow.

UI-resource strings only (see AGENTS.md language contract). Developer-facing
text stays English. Page-specific strings may stay inline when cohesive, but
the primary reading workflow and navigation strings live here.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Navigation / shell

NAV_READING = "阅读"
NAV_HISTORY = "历史"
NAV_KNOWLEDGE = "知识库"
NAV_REVIEW = "复习"
NAV_SETTINGS = "设置"

# ---------------------------------------------------------------------------
# Reading workflow — step 1 (input)

STEP1_TITLE = "读懂这句话"
STEP1_SUBTITLE = "粘贴论文中没有完全理解的英文句子或段落。"
SOURCE_PLACEHOLDER = "在此粘贴英文原句或段落…\nCtrl+Enter 生成提示词"
WORDS_SUFFIX = "词"
CHARS_SUFFIX = "字符"
PAPER_INFO_SECTION = "论文信息（可选）"
PAPER_INFO_HINT = "提供标题 / DOI / 作者后，AI 会尝试联网核实术语与背景"
PREV_CONTEXT_LABEL = "上一段 / 上文"
NEXT_CONTEXT_LABEL = "下一段 / 下文"
PAPER_TITLE_LABEL = "论文标题"
DOI_LABEL = "DOI / URL"
AUTHORS_LABEL = "作者"
DOMAIN_LABEL = "研究领域"
DEPTH_LABEL = "分析深度"
PROFILE_LABEL = "Web AI"
GENERATE_PROMPT = "生成提示词"
LOAD_EXAMPLE = "加载示例"

# ---------------------------------------------------------------------------
# Reading workflow — step 2 (prompt / AI response)

STEP2_TITLE = "提示词已生成"
STEP2_SUBTITLE = "把提示词粘贴到 Web AI，收到回复后回到这里。"
COPY_PROMPT = "复制提示词"
COPIED = "已复制"
VIEW_PROMPT = "查看提示词"
PASTE_RESPONSE_SECTION = "粘贴 AI 返回结果"
RESPONSE_PLACEHOLDER = "把 Web AI 返回的完整内容粘贴到这里（支持 JSON 前后带说明文字）"
PASTE_FROM_CLIPBOARD = "从剪贴板粘贴"
PARSE_RESULT = "解析结果"
BACK_TO_EDIT = "返回修改"

# ---------------------------------------------------------------------------
# Reading workflow — errors

PARSE_ERROR_TITLE = "无法解析 AI 返回结果"
VALIDATION_ERROR_TITLE = "AI 返回内容未通过校验"
GENERATE_ERROR_TITLE = "生成提示词失败"
COPY_REPAIR_PROMPT = "复制修复提示词"
VIEW_RAW_RESPONSE = "查看原始结果"
PROMPT_DIALOG_TITLE = "提示词"
RAW_RESPONSE_DIALOG_TITLE = "原始 AI 结果"

# ---------------------------------------------------------------------------
# Result view

RESULT_TAB_OVERVIEW = "概览"
RESULT_TAB_STRUCTURE = "结构"
RESULT_TAB_GRAMMAR = "语法"
RESULT_TAB_VOCAB = "词汇"
RESULT_TAB_EXPRESSION = "表达"
RESULT_TAB_CONCEPT = "概念"

NATURAL_TRANSLATION_LABEL = "自然翻译"
CORE_MEANING_LABEL = "核心含义"
SENTENCE_SKELETON_LABEL = "句子主干"
LITERAL_TRANSLATION_LABEL = "直译"
TRANSLATION_NOTES_LABEL = "翻译说明"
READING_STRATEGY_LABEL = "阅读策略"
DIFFICULTY_LABEL = "难度"
WHY_DIFFICULT_LABEL = "为什么难"
SENTENCE_TYPE_LABEL = "句型"
REFERENCES_LABEL = "指代关系"
REFERS_TO_LABEL = "指代"
EXPLANATION_LABEL = "解释"
MISUNDERSTANDINGS_LABEL = "易错理解"
WRONG_LABEL = "容易误读成"
WHY_WRONG_LABEL = "为什么错"
CORRECT_LABEL = "正确理解"
READING_TIPS_LABEL = "阅读建议"
WEB_RESEARCH_USED = "AI 联网核实了论文信息"

SEGMENT_DETAIL_TITLE = "片段解读"
SEGMENT_ROLE_LABEL = "语法角色"
SEGMENT_TEXT_LABEL = "原文片段"
SEGMENT_FUNCTION_LABEL = "作用与含义"
SEGMENT_MODIFIES_LABEL = "修饰对象"
SEGMENT_HOW_TO_READ_LABEL = "怎么读"
CLAUSES_LABEL = "从句与修饰"
CLAUSE_TYPE_LABEL = "从句类型"

WORD_IN_CONTEXT_LABEL = "本句含义"
WORD_LEMMA_LABEL = "原形"
WORD_POS_LABEL = "词性"
WORD_WHY_LABEL = "为什么这里这样理解"
WORD_ACADEMIC_LABEL = "学术语境"
WORD_COLLOCATIONS_LABEL = "常见搭配"
WORD_COMMON_MEANINGS_LABEL = "常见含义"
WORD_LEARN_KNOWN = "我认识"
WORD_LEARN_ADD = "加入学习"

PHRASE_MEANING_LABEL = "含义"
PHRASE_USAGE_LABEL = "学术用法"
EXPRESSION_USAGE_LABEL = "用法"
EXPRESSION_WHEN_LABEL = "什么时候用"
CONCEPT_IN_PAPER_LABEL = "在本文中"
CONCEPT_BACKGROUND_LABEL = "建议补充背景知识"
EXAMPLE_LABEL = "例"
PHRASES_GROUP = "短语"
EXPRESSIONS_GROUP = "学术表达"

MASTERY_LABEL = "掌握程度"

# ---------------------------------------------------------------------------
# Empty states

READING_EMPTY_TITLE = "把论文中没看懂的英文放到这里"
READING_EMPTY_SUBTITLE = "先粘贴英文，生成提示词，再把 AI 结果粘贴回来。"
HISTORY_EMPTY_TITLE = "还没有分析记录"
HISTORY_EMPTY_SUBTITLE = "去「阅读」页分析第一句论文吧"
KNOWLEDGE_EMPTY_TITLE = "知识库还是空的"
KNOWLEDGE_EMPTY_SUBTITLE = "分析论文时遇到的单词、短语、语法会自动沉淀到这里"
REVIEW_EMPTY_TITLE = "今天没有到期的复习"
REVIEW_EMPTY_SUBTITLE = "在知识库或阅读页把知识点标记为「不熟 / 不会」，它们会进入学习队列。"
