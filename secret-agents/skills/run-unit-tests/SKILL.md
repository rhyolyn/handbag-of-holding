---
name: run-unit-tests
description: "Run a Python project's unit tests in a managed .venv. Creates the venv if missing, installs all test + pre-commit requirements (pytest, pre-commit, ruff, mypy, etc.), runs the full test suite and pre-commit, and (with --fix) repairs any failing tests or pre-commit violations. Use when the user asks to run unit tests, run the test suite, run pytest, check pre-commit, or says 'rut'."
argument-hint: "[--target <dir>] [--fix] [--help]"
user-invocable: true
---

# Run Unit Tests

**Category:** Testing · **Short:** trut · **Updated:** 2026-10-10 · **Aliases:** rut

Run a Python project's unit tests inside a managed `.venv`. This skill guarantees the
environment exists and is fully provisioned before it runs anything, so it works on a
fresh clone and on a machine where the tools were never installed.

Works on any Python project that has `requirements*.txt` and a `.pre-commit-config.yaml`.
The project root defaults to the current working directory; pass `--target` to point at a
different checkout.

## Invocation / Flags

| Argument | Effect |
|---|---|
| *(none)* | Set up the venv, install deps, run the full test suite + pre-commit, report results. |
| `--target <dir>` | Project root to operate in. Default: the current working directory. |
| `--fix` | As above, but also repair any failing tests and any pre-commit violations, then re-run until clean. |
| `--help` | Print the usage below and stop. Do not set up or run anything. |

### `--help` output

When invoked with `--help`, respond with exactly this usage block and do nothing else:

```
run-unit-tests — run a Python project's unit tests in a managed .venv

Usage:
  /run-unit-tests                     Set up .venv, install deps, run tests + pre-commit
  /run-unit-tests --target <dir>      Operate in the given project root (default: CWD)
  /run-unit-tests --fix               Same, but also fix failing tests & pre-commit violations
  /run-unit-tests --help              Show this help

Short form:
  /rut                                Alias for /run-unit-tests (same flags)

Behavior:
  - Project root = --target when given, else the current working directory
  - Creates .venv in the project root if it does not already exist
  - Installs requirements.txt, requirements/dev.txt, requirements/testing.txt
    plus pre-commit, ruff, and mypy into .venv
  - Runs the full pytest suite (with coverage) and pre-commit
  - With --fix: repairs broken tests / pre-commit errors, re-runs until clean
  - If --fix changed any files, ends with a commit message (< 80 chars) —
    it does NOT stage or commit anything
```

## Procedure

Work from the project root. The project root is the `--target` directory when one is
given, otherwise the current working directory.

```bash
TARGET="<--target value, or the current working directory>"
cd "$TARGET"
```

### Step 1 — Create the virtual environment if missing

```bash
if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
python -m pip install --upgrade pip
```

**Checkpoint:** `python -c "import sys; print(sys.prefix)"` prints a path ending in `.venv`.

### Step 2 — Install all test + pre-commit requirements

Install every requirements file that exists, plus the pre-commit tooling, into the venv:

```bash
pip install -r requirements.txt
[ -f requirements/dev.txt ]      && pip install -r requirements/dev.txt
[ -f requirements/testing.txt ]  && pip install -r requirements/testing.txt
pip install pre-commit ruff mypy
```

**Checkpoint (all must succeed):**

```bash
python -m pytest --version
python -m pre_commit --version
python -m ruff --version
python -m mypy --version
```

If a requirements file is absent, skip it — do not fail.

### Step 3 — Run the full test suite

`pytest.ini` already enables coverage and writes `report.xml` / `coverage.xml`. Run:

```bash
python -m pytest -q
```

**Pass criteria:** final line is `N passed` with `0 failed` and `0 errors`. Skips are fine.

### Step 4 — Run pre-commit

```bash
python -m pre_commit run --all-files
```

**Pass criteria:** every hook reports `Passed` (or `Skipped`). Any `Failed` hook is a
pre-commit error.

### Step 5 — Report

Summarize: test count (passed/failed/errors/skipped), pre-commit hook status, and the
overall verdict (green / red).

## `--fix` behavior

Only when `--fix` is present. After Steps 3–4, if there are failures or pre-commit
errors:

1. **Failing tests** — read each failure, find the root cause in the source (not the
   test), and fix the code. Re-run only the affected test, then the full suite.
2. **Pre-commit violations** — prefer auto-fix first:
   ```bash
   python -m pre_commit run --all-files --hook-stage manual
   ```
   For anything it cannot auto-fix, edit the offending file by hand. Re-run
   `python -m pre_commit run --all-files` until clean.
3. **Fix policy** — never suppress a violation with `# noqa`, `# type: ignore`, or
   config overrides. Fix the code. If a fix is non-obvious or risky, stop and surface
   it to the user instead of guessing.
4. **Re-run the whole gate** (Steps 3 and 4) after fixes to confirm everything is green.

### Commit message (only if `--fix` changed files)

If, during `--fix`, you edited or created any file, end your final response with a
single-line commit message that is **under 80 characters**. Do **not** stage, add, or
commit anything — just provide the message for the user to use.

Format: `type: concise summary` (e.g. `fix: guard discovery walk against unreadable dirs`).
If `--fix` made no changes, do not emit a commit message.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: pytest` | Deps not installed in the active venv | Re-run Step 2 while `.venv` is active |
| `unrecognized arguments: --cov=...` | `pytest-cov` missing | `pip install -r requirements/testing.txt` |
| `PermissionError` reading a source file on Windows | Test read a file with the platform default encoding (cp1252) | Read source files with `encoding="utf-8"` in the test |
| `python3 -m venv` fails | Missing `ensurepip` (some distros) | `xcode-select --install` / install `python3-venv`, then retry |
| pre-commit hook `Failed` on line endings | CRLF in a checked-in file | `python -m pre_commit run mixed-line-ending --all-files` |
