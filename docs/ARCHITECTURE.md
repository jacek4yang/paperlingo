# Architecture

PaperLingo is a Windows-first desktop application (Python 3.13, PyQt6 Qt Widgets,
standard-library sqlite3, Pydantic v2) that turns an English academic sentence into a
structured, interactive learning experience via a manual web-AI workflow.

## Layers

```
UI (PyQt6, ui/)                pages, widgets, theme; never touches SQL
        |
Domain models (domain/)        Pydantic models: PaperAnalysis, AnalysisRequest, learning enums
        |
Prompt compiler (prompt/)      English-only AI instructions; per-model profiles
Response parser (parser/)      tolerant JSON extraction + bounded syntax repair
        |
Repository (database/)        all SQL; transactions; migrations
        |
Learning/review (learning/)    Scheduler interface (SM-2 style default), FSRS-replaceable
```

## UI layer

- `ui/main_window.py` hosts a navigation rail (阅读 / 历史 / 知识库 / 复习 / 设置)
  plus a `QStackedWidget` of pages.
- The reading page implements the sequential workflow (enter English -> prompt + AI
  response -> analysis) as internal states.
- `ui/widgets/result_view.py` renders the analysis with progressive disclosure:
  hero content (original sentence, natural translation, core meaning, skeleton) plus
  a segmented navigation where each category is a list-plus-detail view.
- `ui/widgets/sentence.py` maps AI-returned segments/clauses onto the exact source
  text (strict matching; unmatched segments are simply not highlighted) and renders
  program-generated HTML with escaped source text only.
- All labels shown to the user are centralized Simplified Chinese strings; internal
  values passed into prompts are stable English identifiers.

## Domain models

`domain/analysis.py` defines the Pydantic schema (`PaperAnalysis`, `SCHEMA_VERSION`)
that AI responses must satisfy, with defensive caps on text length and list sizes.
`AnalysisRequest` carries everything the prompt compiler consumes. `domain/learning.py`
defines item types, mastery status (`known`/`unfamiliar`/`hard`), and review ratings
(`again`/`hard`/`good`/`easy`) with Chinese display labels kept separate.

## Prompt compiler

`prompt/templates.py` holds versioned templates assembled from parts (role, web
research policy, context, paper info, learner profile, task, depth, output protocol,
schema description). `prompt/profiles.py` adds per-model adjustments (generic,
ChatGPT, Claude, Grok, Gemini). Every static instruction is English; the prompt
requests explanations in natural Simplified Chinese. The repair prompt embeds the raw
failed response in ASCII-escaped form (`json.dumps(..., ensure_ascii=True)`) so repair
instructions stay English while preserving the Chinese payload byte-for-byte.

## Response parser

`parser/response_parser.py` pre-processes (BOM, zero-width characters, line endings),
then tries strict parse, Markdown-fenced extraction, and balanced-brace extraction,
with `parser/repair.py` applying only form-level repairs (smart quotes, trailing
commas, closing unterminated brackets). Syntax repair only; semantic fabrication
never. The extracted dict is validated by Pydantic before reaching the UI.

## Repository / database layer

`database/db.py` owns the sqlite3 connection (foreign keys, busy timeout, WAL),
portable path resolution, and idempotent close (commit, `PRAGMA optimize`, WAL
checkpoint, close). `database/migrations.py` holds ordered migrations tracked by
`PRAGMA user_version`. `database/repository.py` contains all SQL: analyses, papers,
knowledge tables with lemma+POS word deduplication and occurrence counting, settings,
drafts, learning items, review logs, and export. Analysis save plus knowledge
ingestion runs inside one explicit transaction.

## Learning / review layer

`learning/review.py` isolates scheduling behind a `Scheduler` protocol with a
dependency-free SM-2 style default. Due times and review logs persist in
`learning_items` / `review_logs`.

## Persistence lifecycle

Packaged app: database is `paperlingo.db` beside `PaperLingo.exe`; if the directory is
not writable the app shows a Chinese error including the path and exits. Development:
a deterministic project-local path derived from the source tree. Shutdown commits
pending work, runs `PRAGMA optimize`, checkpoints WAL, and closes via both
`aboutToQuit` and a `finally` block.

## Build / package flow

`scripts/build.ps1`: uv sync --frozen -> ruff -> pytest -> clean build/dist ->
PyInstaller (one-folder, via `paperlingo.spec`) -> verify `dist/PaperLingo/PaperLingo.exe`
-> short smoke launch. CI runs the same quality gates and a real packaging job on
`windows-latest`.

## Security boundary around AI output

AI responses are untrusted: JSON extraction -> Pydantic validation -> domain model ->
plain-text rendering. AI strings that are interpolated into program-generated HTML are
always escaped. There is no eval/exec, no model API integration, and no automatic
remote content loading.
