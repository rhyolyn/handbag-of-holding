---
name: python-tdd-cycle
description: Use when implementing any new feature or fix in a Python project that uses pytest. Enforces the red-green loop: write failing tests first, confirm they fail, implement, confirm they pass, then run the full suite before committing.
---

# Python TDD Cycle

Use this skill for every implementation task in a pytest-based Python project.

## The Loop

For each unit of work (one task, one class, one behavior):

1. **Write the test(s) first.** Target the narrowest scope that proves the behavior. Do not implement anything yet.
2. **Confirm red.** Run only the new test file:
   ```
   python -m pytest tests/path/test_new.py -v
   ```
   The test must fail. If it passes without implementation, the test is wrong — fix it before continuing.
3. **Implement** the minimum source change to make the test pass. Do not add anything beyond what the test requires.
4. **Confirm green.** Run the same file again:
   ```
   python -m pytest tests/path/test_new.py -v
   ```
   All new tests must pass.
5. **Run the full suite** to catch regressions:
   ```
   python -m pytest --tb=short -q
   ```
   All tests must pass before proceeding to commit.

## Windows note

On this project `uv run pytest` may fail with an access-denied error if `ugs.exe` is locked by a running process. Fall back to `python -m pytest` — it bypasses the uv build step and works regardless.

## What counts as done

- New tests exist and were observed failing before implementation.
- Full suite passes after implementation.
- No tests were skipped or suppressed to achieve a green run.

## What this skill does NOT cover

Committing the result — use the project's conventional commit pattern (co-author trailer, etc.) after the suite is green.
