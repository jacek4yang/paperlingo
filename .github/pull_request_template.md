<!--
English PR title, e.g. "feat: finish PaperLingo v0.1.0".
See AGENTS.md for the authoritative development contract.
-->

## Scope

<!-- What does this PR change and why? Reference related issues. -->

## Tests

- [ ] `uv run pytest` passes locally
- [ ] New/changed behavior is covered by tests (or N/A)

## Ruff

- [ ] `uv run ruff check src tests` passes
- [ ] No new ignore rules added (or justified below)

## UI impact

- [ ] Affected flows manually validated in the running app
- [ ] Validated in both light and dark themes (or no UI change)
- [ ] User-facing text is Simplified Chinese; no decorative emoji navigation

## Database migration

- [ ] Schema change includes an explicit migration + upgrade test (or no schema change)

## Prompt-language contract

- [ ] Generated prompts remain English-only instructions; no CJK in compiled prompts
      for English input; repair prompt uses ASCII-safe payload (or prompt layer untouched)

## Packaging impact

- [ ] `.\scripts\build.ps1` verified (or change cannot affect packaging)

## Security impact

- [ ] AI/user-controlled strings are escaped or rendered as plain text
- [ ] No eval/exec, no automatic remote loading, no new network behavior
