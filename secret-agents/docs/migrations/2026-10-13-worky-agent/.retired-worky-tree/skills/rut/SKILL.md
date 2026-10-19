---
name: rut
description: "Short alias for the run-unit-tests skill. Run a Python project's unit tests in a managed .venv — creates the venv if missing, installs all test + pre-commit requirements, runs the full suite and pre-commit, and (with --fix) repairs failures. Use when the user types 'rut' or asks for the quick unit-test run."
argument-hint: "[--target <dir>] [--fix] [--help]"
user-invocable: true
---

# rut (run-unit-tests, short form)

`/rut` is the short alias for the `run-unit-tests` skill. It performs the exact same
workflow. If the `run-unit-tests` skill is available, follow it; otherwise follow the
self-contained procedure below.

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
rut — short form of run-unit-tests

Usage:
  /rut                        Set up .venv, install deps, run tests + pre-commit
  /rut --target <dir>         Operate in the given project root (default: CWD)
  /rut --fix                  Same, but also fix failing tests & pre-commit violations
  /rut --help                 Show this help

Equivalent to:
  /run-unit-tests [--target <dir>] [--fix] [--help]

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
