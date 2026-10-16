---
name: python-quality-gate
description: Use before committing any Python change, after implementing or fixing Python code, or as the final check before opening a PR in a Python repository.
---

# Python Quality Gate

**Category:** Code Quality · **Updated:** 2026-10-15

Run the full gate after every implementation and before every commit.

## Which gate to run

If the repository documents its own quality gate (its AGENTS.md, CLAUDE.md, README, or CI configuration), run that gate exactly as documented — every command, in the documented order. A documented gate supersedes this skill's default, including any extra commands it adds.

Otherwise run the four-tool default in order — type errors first, then lint, then format, then tests:

```
python -m mypy
python -m ruff check <src-dirs> <test-dirs>
python -m ruff format --check <src-dirs> <test-dirs>
python -m pytest --tb=short -q
```

Discover `<src-dirs>` and `<test-dirs>` from the repository layout (`src/`, `tests/`, `test/`, or the package directories); pass the same paths to both ruff commands. If `uv run` is available it may substitute for `python -m` — they are equivalent.

## Pass criteria

Every command must exit clean:

- `mypy`: `Success: no issues found in N source files` — treat `N = 0` as a gate failure; a scan of nothing proves nothing, fix the mypy configuration instead.
- `ruff check`: `All checks passed!`
- `ruff format --check`: `N files already formatted` — if only this check fails, run `ruff format` on the same paths, then re-run the full gate.
- `pytest`: `N passed` (zero failures, zero errors)

## Fix policy

- **Never suppress** a violation with `# type: ignore`, `# noqa`, or rule-selection overrides unless you have explicit user approval.
- Fix the code. If a fix is non-obvious, surface it to the user rather than suppressing.
- Repository-specific fix recipes and tool quirks belong in that repository's own AGENTS.md, not in this shared skill.

## When to run

- After implementing each task's source changes (before staging).
- After fixing any violation (re-run the full gate, not just the tool that flagged).
- As a final check before opening a PR.
