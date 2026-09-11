# Contributing to PaperLingo

Thanks for contributing. This repository is developed by a solo developer with AI
agents, so the rules below keep the workflow simple and safe.

## Getting started

```powershell
# Install uv (https://docs.astral.sh/uv/), then:
uv sync
uv run python -m paperlingo   # run the app
uv run ruff check src tests   # lint
uv run pytest                 # tests
```

Python 3.13+ is required. `uv` is the only supported project runner — do not use pip.

## Workflow

1. Read `AGENTS.md` first. It is the authoritative contract: technology constraints,
   the language contract (UI in Simplified Chinese, developer-facing content and
   generated LLM prompts in English), database rules, and security boundaries.
2. Create a feature branch. Do not push directly to `main` — it is protected and
   requires the CI checks to pass through a pull request.
3. Commit in small logical units with English commit messages
   (`fix: ...`, `feat: ...`, `refactor: ...`, `ui: ...`, `test: ...`, `docs: ...`).
4. Open a pull request into `main` using the PR template and fill in every section.
5. Wait for the required checks (`quality`, `windows-package`) to pass, resolve any
   conversations, and squash-merge.

## Before you open a PR

- `uv run ruff check src tests` passes.
- `uv run pytest` passes. Do not delete or weaken a failing test to get green CI.
- If you changed UI, launch the app and manually verify the affected flow in both
  light and dark themes.
- If you changed the database schema, add a migration and a test that upgrades from
  the previous schema. Never destroy existing user databases.
- If you touched the prompt layer, generated prompts must remain English-only
  instructions (Simplified Chinese is only requested as the AI's output language).
  The prompt-language regression test must stay green.
- If the change affects packaging or the database lifecycle, run
  `.\scripts\build.ps1` and verify `dist\PaperLingo\PaperLingo.exe` launches and
  creates its database beside itself.

## Code style

- Match the surrounding code. Type hints, docstrings, and comments are English.
- Chinese strings shown to users are centralized where practical.
- Ruff rules are configured in `pyproject.toml`. Fix real problems; do not expand
  ignores. `noqa` is only for genuine framework/API exceptions.

## Security

AI responses are untrusted input. Anything involving parsing, HTML rendering, URL
handling, or file/database handling is security relevant — see `SECURITY.md`.
