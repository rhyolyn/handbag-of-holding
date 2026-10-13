---
name: rut
description: Alias for run-unit-tests. Run a Python project's unit tests in a managed .venv. Creates the venv if missing, installs all test + pre-commit requirements (pytest, pre-commit, ruff, mypy, etc.), runs the full test suite and pre-commit, and (with --fix) repairs any failing tests or pre-commit violations. Use when the user asks to run unit tests, run the test suite, run pytest, check pre-commit, or says 'rut'.
---

<!-- generated:run-unit-tests:2026-10-12 -->
# rut

Alias for `run-unit-tests`. Pass all arguments through unchanged.

## Behavior

Follow the `run-unit-tests` skill exactly. Treat all arguments passed to `/rut` as arguments for `/run-unit-tests`.
