"""Prompt template system.

Templates are not one hard-coded blob: each template has a version and is assembled
from ordered parts. Tests verify placeholders and compiled output. Upgrades to the
analysis protocol add new template versions.

Language contract: every instruction in this file is English-only. The compiled
prompt must tell the AI, in English, to write explanatory fields in natural
Simplified Chinese. No Chinese may appear in any template; a regression test
enforces this (tests/test_prompt.py::test_no_cjk_in_compiled_prompts).
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Current default analysis template version
DEFAULT_TEMPLATE_ID = "paper_analysis_v1"

#: Repair prompt template version
REPAIR_TEMPLATE_ID = "repair_v1"


@dataclass(frozen=True)
class PromptTemplate:
    template_id: str
    version: str
    #: Ordered list of parts; each part is text with {placeholder} markers.
    parts: tuple[str, ...]
    description: str = ""
    #: All placeholders allowed in this template (validated at compile time).
    placeholders: frozenset[str] = field(default_factory=frozenset)


# ---------------------------------------------------------------------------
# Parts of paper_analysis_v1
# ---------------------------------------------------------------------------

_ROLE = """\
You are simultaneously:
1. an academic English expert,
2. a linguistics expert,
3. an expert in reading research papers,
4. {domain_role}.

The person you serve is a native Chinese speaker learning to read academic English.
Write all explanatory fields in natural Simplified Chinese: clear and idiomatic,
not a pile of linguistic jargon. The goal is that the student genuinely understands
the sentence, not that they can recite grammar terminology.
"""

_WEB_RESEARCH = """\
[Paper identification and web research]
{web_research_instruction}
"""

_WEB_RESEARCH_WITH_INFO = """\
The user provided paper information (title/DOI/URL/authors). If your environment
supports web search:
1. Search for and confirm the original paper first;
2. Read the necessary surrounding context to understand the authors' true meaning;
3. Prefer the paper itself and reliable academic sources;
4. Never mistranslate domain terms just because a generic dictionary sense exists;
5. If you cannot find the paper, say so explicitly in web_research.notes and never
   fabricate sources;
6. Web results are only used to improve understanding quality. They must never
   overwrite or modify the user-provided source text.
Fill in web_research.used / paper_identified / notes / sources truthfully.
If you cannot search the web, set web_research.used to false and analyze the given
text directly.
"""

_WEB_RESEARCH_NO_INFO = """\
The user did not provide enough information to locate the paper. If you believe
searching the web for the paper would significantly improve understanding quality,
and your environment supports it, you may try; otherwise set web_research.used to
false and analyze the given text directly. Never fabricate sources.
"""

_CONTEXT = """\
[Text to analyze]
The text below is the ONLY object of analysis. Quote it verbatim; never modify it.
<source_text>
{source_text}
</source_text>

{context_block}\
"""

_CONTEXT_PREV = """\
[Previous context (for understanding only; not to be analyzed)]
<previous_context>
{previous_context}
</previous_context>
"""

_CONTEXT_NEXT = """\
[Following context (for understanding only; not to be analyzed)]
<following_context>
{following_context}
</following_context>
"""

_PAPER_INFO = """\
[Paper information]
{paper_info_lines}
"""

_PROFILE_HEADER = "[Learner profile (for reference only; never skip core structural analysis because of it)]"

_TASK = """\
[Task]
Analyze the English in <source_text> with the following priorities:
1. Understand precisely what the author really means.
2. Translate accurately (distinguish literal from natural translation; avoid
   translationese).
3. Break down the long/difficult sentence structure (subject, predicate, object,
   clauses, modification relations).
4. Explain the grammar points that most trip up native Chinese speakers.
5. Explain what each word means "in this sentence" (not the first dictionary sense).
6. Extract fixed collocations and academic writing expressions worth learning.
7. Analyze coreference (it/this/these/they/which/that/such/the former/the latter etc.).
8. Explain domain concepts (distinguish "does not know the English" from "knows the
   English but not the domain knowledge").
9. Point out typical misreadings by Chinese students.

Do not waste space on basic words such as "the / a / is / of / and" one by one,
unless one plays a key role in a special grammatical structure.

All teaching explanations should answer, first and foremost:
- Why? What structure is this, exactly?
- Where should a reader start reading?
- Which part can be skipped first?
- Which part modifies which part?
- Why can it not be understood in the literal word order?
- How to quickly recognize a similar structure next time?
Do not give bare terminology labels. For example, do not just write "this is a
non-restrictive relative clause"; also write "you may bracket it while reading,
finish the main clause first, then come back for this extra information".
"""

_DEPTH_QUICK = """\
[Analysis depth: quick understanding]
The user just wants to understand this sentence quickly. Requirements:
- translation.natural / core_meaning must be of high quality;
- overview is required;
- syntax: give only structure_summary, skeleton, and the 3-8 most essential segments;
- grammar_points: at most 1 (only the most blocking one);
- words: at most 3 (only those that truly block understanding);
- phrases / academic_expressions: at most 2 each;
- references: only those that affect understanding;
- concepts: at most 2; misunderstandings: at most 1;
- reading_tips: 1 is enough.
"""

_DEPTH_STANDARD = """\
[Analysis depth: standard]
Give a complete but restrained analysis:
- Fill every top-level field conscientiously, but never fabricate content just to
  fill the schema;
- words: at most 8, only those worth learning;
- grammar_points: at most 4;
- phrases / academic_expressions: at most 4 each;
- concepts: at most 4; misunderstandings: at most 3.
"""

_DEPTH_DEEP = """\
[Analysis depth: deep learning]
The user wants to master this sentence thoroughly. On top of the standard depth:
- syntax.segments must cover all key constituents of the sentence; clauses complete;
- write why_used_here and common_mistake clearly for every grammar_point;
- words / phrases may be richer, but still exclude basic words;
- reading_tips: give reading methods transferable to other papers;
- if appropriate, anticipate the most typical misreading by a Chinese student in
  misunderstandings.
"""

_OUTPUT = """\
[Output protocol (strict)]
1. Output exactly one JSON object as your final answer. No Markdown headings,
   explanations, or comments.
2. Do not wrap the JSON in a ```json code block; output the JSON itself.
3. Strings containing newlines must be correctly escaped.
4. Fill schema_version exactly as "{schema_version}".
5. Use null or [] for anything you cannot determine. NEVER fabricate content just
   to fill the schema.
6. Write all explanatory fields in natural Simplified Chinese. Keep JSON property
   names in English. source_text, segments.text, clauses.text, words.surface,
   phrases.text, and references.expression must be copied verbatim from the English
   source text so they can be located exactly in it (case-sensitive).
7. Do not output HTML / CSS / code; plain text only.

The JSON structure is as follows (property names must match exactly):
{schema_description}
"""

#: Schema description shown to the AI (manually maintained, kept in sync with
#: domain/analysis.py; a test verifies the field names match).
SCHEMA_DESCRIPTION = """\
{
  "schema_version": "1.0",
  "source_text": "<the original text copied verbatim>",
  "translation": {
    "natural": "<accurate and natural Simplified Chinese translation (most important)>",
    "literal": "<literal translation that keeps the English structure>",
    "core_meaning": "<explain the author's intended meaning in Simplified Chinese (1-2 sentences)>",
    "translation_notes": ["<reasons for key translation decisions>"]
  },
  "overview": {
    "difficulty": <integer 1-5>,
    "difficulty_reason": "<why this difficulty>",
    "sentence_type": "<sentence type, e.g. compound-complex sentence>",
    "one_sentence_explanation": "<what this sentence is doing, in one sentence>",
    "reading_strategy": "<strategy for reading this kind of sentence>"
  },
  "syntax": {
    "structure_summary": "<e.g. main clause + relative clause + adverbial of manner>",
    "skeleton": "<the sentence skeleton with modifiers removed (English)>",
    "main_clause": {"subject": "", "predicate": "", "object": "", "complement": "", "summary_zh": "<Simplified Chinese summary of the skeleton>"},
    "segments": [{"text": "<verbatim source fragment>", "role": "<English role such as subject>", "role_zh": "<role label in Simplified Chinese>", "explanation": "<what this fragment does and means>"}],
    "clauses": [{"text": "<clause verbatim>", "type": "<e.g. relative_clause>", "type_zh": "<type label in Simplified Chinese>", "modifies": "<what it modifies>", "explanation": "<explanation>"}]
  },
  "grammar_points": [{
    "name": "<e.g. allow + object + to do>", "name_zh": "<name in Simplified Chinese>",
    "source": "<verbatim fragment where it appears>",
    "explanation": "<teach until the student truly understands; do not just stick on a label>",
    "why_used_here": "<why the author uses it here>",
    "simple_example": "<a simple English example>", "simple_example_zh": "<the example in Simplified Chinese>",
    "common_mistake": "<the most common misunderstanding by Chinese students>",
    "importance": <integer 1-5>
  }],
  "words": [{
    "surface": "<form as it appears in the text>", "lemma": "<base form>", "phonetic": "<phonetic, leave empty if unsure>",
    "pos": "<e.g. adjective>", "pos_zh": "<part of speech in Simplified Chinese>",
    "meaning_in_context": "<meaning in this sentence (most important)>",
    "common_meanings": ["<common senses>"], "academic_meaning": "<meaning in academic contexts>",
    "why_here": "<why it must be understood this way here>",
    "collocations": ["<common collocations>"], "difficulty": <integer 1-5>, "worth_learning": true
  }],
  "phrases": [{
    "text": "<verbatim phrase>", "meaning": "<meaning in Simplified Chinese>", "explanation": "<explanation>",
    "academic_usage": "<usage in academic writing>", "example": "<example>", "example_zh": "<the example in Simplified Chinese>",
    "worth_learning": true
  }],
  "academic_expressions": [{
    "text": "<expression commonly used in paper writing>", "meaning": "<meaning in Simplified Chinese>",
    "usage": "<usage notes>", "when_to_use": "<when it can be used in the student's own writing>",
    "example": "<example>", "example_zh": "<the example in Simplified Chinese>"
  }],
  "references": [{"expression": "they", "refers_to": "<what the expression refers to>", "explanation": "<explanation>"}],
  "concepts": [{
    "term": "<e.g. prompt injection>", "translation": "<the term in Simplified Chinese>",
    "simple_explanation": "<plain explanation for a non-expert reader>",
    "meaning_in_this_paper": "<concrete meaning in this paper>",
    "background_needed": false
  }],
  "misunderstandings": [{
    "wrong_interpretation": "<typical wrong reading>", "why_wrong": "<why it is wrong>",
    "correct_interpretation": "<correct reading>"
  }],
  "reading_tips": ["<transferable reading advice>"],
  "web_research": {
    "used": false, "paper_identified": false, "notes": "",
    "sources": [{"title": "", "url": ""}]
  }
}
"""

#: Repair prompt: handed back to the AI when response parsing fails.
#: {raw_response_excerpt} is injected as an ASCII-safe JSON-escaped string by
#: compile_repair_prompt so the template itself stays English-only.
REPAIR_TEMPLATE = """\
The analysis result you returned last time could not be parsed by the program as
valid JSON.

Parse error:
{error}

{raw_response_excerpt}

Please output again: a single complete, valid JSON object that conforms to the
schema you were given before (schema_version = "{schema_version}").
Repair JSON syntax only. Do not re-analyze the academic sentence.
Do not change any semantic content of your previous answer.
Return only valid JSON itself: no Markdown, no explanations, no code block markers.
"""

# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

TEMPLATES: dict[str, PromptTemplate] = {
    DEFAULT_TEMPLATE_ID: PromptTemplate(
        template_id=DEFAULT_TEMPLATE_ID,
        version="1.0.0",
        description="Deep analysis of a paper sentence/paragraph (v1 protocol)",
        parts=(
            _ROLE,
            _WEB_RESEARCH,
            _CONTEXT,
            _PAPER_INFO,
            "{knowledge_profile_block}",
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
                "knowledge_profile_block",
                "depth_instruction",
                "schema_version",
                "schema_description",
            }
        ),
    ),
    REPAIR_TEMPLATE_ID: PromptTemplate(
        template_id=REPAIR_TEMPLATE_ID,
        version="1.0.0",
        description="Repair prompt for a failed AI response parse",
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
