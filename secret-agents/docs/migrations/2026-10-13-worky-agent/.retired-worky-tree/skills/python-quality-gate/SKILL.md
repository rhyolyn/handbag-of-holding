---
name: python-quality-gate
description: Use before committing any Python change. Runs the four-tool gate in order — mypy, ruff check, ruff format --check, pytest — and requires all four to pass clean before the commit is allowed. Fix violations in code; never suppress.
---

# Python Quality Gate

Run this gate after every implementation and before every commit. The order matters: type errors first, then lint, then format, then tests.

## Commands

```
python -m mypy
python -m ruff check src/ tests/
python -m ruff format --check src/ tests/
python -m pytest --tb=short -q
```

If `uv run` is available and `ugs.exe` is not locked, you may substitute `uv run` for `python -m` — they are equivalent. On Windows with an active process holding the binary, `python -m` is the safe fallback.

## Pass criteria

All four commands must exit clean:
- `mypy`: `Success: no issues found in N source files`
- `ruff check`: `All checks passed!`
- `ruff format --check`: `N files already formatted`
- `pytest`: `N passed` (zero failures, zero errors)

## Fix policy

- **Never suppress** a violation with `# type: ignore`, `# noqa`, or `select = []` overrides unless you have explicit user approval.
- Fix the code. If a fix is non-obvious, surface it to the user rather than suppressing.
- Common patterns seen on this project:
  - ruff B008 (`QModelIndex()` as default arg) → use `None` sentinel with `0 if parent is not None and parent.isValid() else ...`
  - mypy `T | None` from `findChild` → add `assert widget is not None` guard before use
  - mypy on `QCoreApplication.instance()` → split into two lines with assertion

## When to run

- After implementing each task's source changes (before staging).
- After fixing any violation (re-run the full gate, not just the tool that flagged).
- As a final check before opening a PR.
