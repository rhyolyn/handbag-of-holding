---
name: run-mac-coverage
description: Use when running, validating, or debugging Scout Mac LLVM code coverage on a Mac test runner. Covers getting/installing the latest laika-build-unreal, running the coverage pipeline, verifying generated reports (HTML, LCOV, text, summary), and troubleshooting common failures.
argument-hint: "[--target <dir>] [--package <dir>] [--help]"
user-invocable: true
---

# Run Mac Coverage

**Category:** Testing · **Short:** trmc · **Updated:** 2026-10-10

## Overview

Run Scout C++ code coverage on a Mac using the `laika-build-unreal` coverage pipeline. The pipeline builds `ScoutingAppEditor` with LLVM instrumentation, runs automation tests, merges profiles, and generates HTML/LCOV/text reports.

Core rule: run from the UE source root, use the `laika-build-unreal` package on `PYTHONPATH`, and verify all four report types after each run.

## Invocation / Flags

| Argument | Effect |
|---|---|
| *(none)* | Use the current working directory as the UE source root; the package is its sibling `laika-build-unreal`. |
| `--target <dir>` | UE source root (the `root` checkout you build and test from). Default: CWD. |
| `--package <dir>` | `laika-build-unreal` checkout. Default: `<target>/../laika-build-unreal`. |
| `--help` | Print usage and stop. |

Set these once, then every step below uses `$TARGET` (UE root) and `$PACKAGE`
(the package). Relative paths resolve from the CWD.

## Paths

| Item | Path |
|---|---|
| laika-build-unreal (`$PACKAGE`) | `<--package value, or <target>/../laika-build-unreal>` |
| UE source root (`$TARGET`) | `<--target value, or the current working directory>` |
| PYTHONPATH | `$PACKAGE/src` |
| Coverage outputs | `$TARGET/scout_coverage/` |
| Editor binary | `Content/ScoutingApp/Binaries/Mac/ScoutingAppEditor.app/Contents/MacOS/ScoutingAppEditor` |
| Instrumented dylib | `Content/ScoutingApp/Binaries/Mac/libScoutingAppEditor-ScoutingApp.dylib` |
| profdata | `scout_coverage/scoutingapp.profdata` |
| Text report | `scout_coverage/mac-coverage.txt` |
| LCOV | `scout_coverage/scoutingapp.lcov` |
| HTML | `scout_coverage/mac-html/index.html` |
| Summary | `scout_coverage/mac-coverage-summary.md` |
| Automation log | `scout_logs/mac_coverage_automation.log` |

## Step 1 — Get and install the latest laika-build-unreal

```bash
cd "$PACKAGE"
git pull
```

The package is stdlib-only (no third-party runtime deps). Two ways to make it importable:

**Option A — PYTHONPATH (preferred for local runs):**

```bash
export PYTHONPATH="$PACKAGE/src:$PYTHONPATH"
```

**Option B — pip editable install:**

```bash
cd "$PACKAGE"
pip install -e .
```

**Checkpoint:** `python3 -c "import laika_build_unreal; print(laika_build_unreal.__file__)"` prints a path under `$PACKAGE/src/`.

## Step 2 — Verify prerequisites

```bash
cd "$TARGET"

# LLVM tools discoverable via xcrun
xcrun --find llvm-cov
xcrun --find llvm-profdata
xcrun --find llvm-nm

# Project file exists
ls Content/ScoutingApp/ScoutingApp.uproject

# Editor binary exists (or will be built)
ls Content/ScoutingApp/Binaries/Mac/ScoutingAppEditor.app/Contents/MacOS/ScoutingAppEditor 2>/dev/null \
  || echo "Editor not built yet — Step 3 will build it"

# Disk space (~5 GB free)
df -h "$TARGET"
```

**Checkpoint:** All three `xcrun --find` commands print a path. The `.uproject` file exists.

If `xcrun --find llvm-cov` fails: `xcode-select --install`

## Step 3 — Run coverage

### Full run (build + test + report)

```bash
cd "$TARGET"
export PYTHONPATH="$PACKAGE/src:$PYTHONPATH"
python3 -m laika_build_unreal.run_mac_coverage "Scout."
```

**Expected duration:** 15–40 minutes (build dominates).

### Fast iteration (skip build)

Once the editor binary and instrumented dylib exist on disk:

```bash
cd "$TARGET"
export PYTHONPATH="$PACKAGE/src:$PYTHONPATH"
python3 -m laika_build_unreal.run_mac_coverage --skip-build "Scout."
```

**Expected duration:** 2–5 minutes.

### Run a subset of tests

```bash
python3 -m laika_build_unreal.run_mac_coverage --skip-build "Scout.MySpecificTest"
```

**Checkpoint:** Exit code is `0`. The console prints `Mac coverage summary` with matched/passed counts and report paths.

## Step 4 — Verify the reports

All four report types must be present and non-zero:

```bash
cd "$TARGET/scout_coverage"

# 1. List all artifacts
ls -la
# Expected: mac-html/, scoutingapp.lcov, scoutingapp.profdata,
#           mac-coverage.txt, mac-coverage-summary.md, profiles/

# 2. Text report — TOTAL row must be non-zero
tail -5 mac-coverage.txt
# Expected: TOTAL 5464 ... 68.41% ... 87.92% ... 80.18% ... 51.39%

# 3. Summary — Overall Coverage table must be non-zero
grep -A6 "Overall Coverage" mac-coverage-summary.md
# Expected: Lines ~80%, Functions ~88%, Regions ~68%, Branches ~51%

# 4. LCOV — files must be under Content/ScoutingApp/Source/
grep -c "^SF:" scoutingapp.lcov
grep "^SF:" scoutingapp.lcov | grep -c "Content/ScoutingApp/Source"
# Both counts should be ~40 (31 .cpp + 9 .h)

# 5. HTML — index.html must exist
ls -la mac-html/index.html
```

**Expected coverage (validated 2026-10-09):**

| Type | Covered | Total | Percent |
|---|---|---|---|
| Lines | 2,091 | 2,608 | 80.18% |
| Functions | 291 | 331 | 87.92% |
| Regions | 3,738 | 5,464 | 68.41% |
| Branches | 777 | 1,512 | 51.39% |

**Expected source files:** ~40 (31 `.cpp` + 9 `.h`), all under `Content/ScoutingApp/Source/ScoutingApp/`.

## Step 5 — Troubleshooting

### Exit code 2 (setup error)

| Symptom | Cause | Fix |
|---|---|---|
| `llvm-cov was not found` | Xcode CLT not installed | `xcode-select --install` |
| `Missing required coverage input: .../ScoutingAppEditor` | Editor not built | Run without `--skip-build` |
| `Build completed but editor binary was not deployed` | UBT succeeded but binary missing | Check UBT log; re-run without `--skip-build` |
| `Missing required coverage input: .../ScoutingApp.uproject` | Wrong repo root | `cd "$TARGET"` |

### Exit code 1 (validity gate failed)

| Symptom | Cause | Fix |
|---|---|---|
| `No raw coverage profiles were generated` | Tests didn't run or `LLVM_PROFILE_FILE` not set | Check `scout_logs/mac_coverage_automation.log` |
| `Only empty raw coverage profiles` | Instrumented binary ran but didn't flush counters | Rebuild without `--skip-build` |
| `No Mac project coverage binaries were found` | Module dylibs missing or not instrumented | Rebuild; check `Content/ScoutingApp/Binaries/Mac/` for `*.dylib` |
| `Total functions: 0` | Profile merged but contains no data | Check raw profile sizes: `ls -la scout_coverage/profiles/` |
| `Missing TOTAL row` / `zero analyzed files` | `llvm-cov` couldn't match source paths | Verify `Content/ScoutingApp/Source` exists and is readable |

### Reports not generated (pipeline returns early)

If the pipeline prints `Mac coverage summary` but no reports are generated, the `was_successful` gate failed. Check:

1. **Matched tests > 0** — the filter matched at least one test
2. **Automation exit code = 0** — the editor exited cleanly
3. **Failed count = 0** — no tests failed

The engine emits `Found N automation tests` and `TEST COMPLETE. EXIT CODE: 0` but does not always emit a parseable `Passed: N` line. The `was_successful` property in `models/coverage.py` must accept `passed_count == 0` as valid when `failed_count == 0` and `automation_exit_code == 0`. If you see `Passed: 0` in the summary but reports are missing, verify this fix is present.

### Mismatched-data warnings (non-fatal)

`llvm-cov` may print `warning: N functions have mismatched data`. This is **non-fatal** — the pipeline prints a warning and continues. Coverage numbers may be slightly affected but reports are still generated.

If the warning is large (>10000 functions), verify:
- The `--object` flag reaches `llvm-cov` for each module dylib
- The dylib has coverage symbols: `xcrun llvm-nm <dylib> | grep llvm_profile`

### Build fails

```bash
# Check the UBT log
tail -100 "$TARGET/Engine/Programs/UnrealBuildTool/Log.txt"

# Common fix: stale UBA session (override UBA_HOME if your build home differs)
ls "${UBA_HOME:-$HOME/.epic/UnrealBuildAccelerator}/sessions/"
# Remove stale sessions, then retry:
python3 -m laika_build_unreal.run_mac_coverage --no-uba "Scout."
```

### Coverage is 0%

This was the original bug. Verify the fix is active:

```bash
cd "$TARGET"

# 1. Module dylibs exist (note the lib prefix)
find Content/ScoutingApp/Binaries/Mac -name "libScoutingAppEditor-ScoutingApp*.dylib" -o -name "libUnrealEditor-ScoutingApp*.dylib"

# 2. Coverage symbols present (use nm without -g; coverage symbols are local)
xcrun llvm-nm Content/ScoutingApp/Binaries/Mac/libScoutingAppEditor-ScoutingApp.dylib | grep llvm_profile

# 3. Editor binary exists
ls Content/ScoutingApp/Binaries/Mac/ScoutingAppEditor.app/Contents/MacOS/ScoutingAppEditor
```

If any are missing, rebuild from scratch (Step 2 clean + Step 3 full run).

### Manual llvm-cov validation

To independently verify coverage data without the pipeline:

```bash
cd "$TARGET"
xcrun llvm-cov report \
  Content/ScoutingApp/Binaries/Mac/ScoutingAppEditor.app/Contents/MacOS/ScoutingAppEditor \
  --instr-profile=scout_coverage/scoutingapp.profdata \
  --object Content/ScoutingApp/Binaries/Mac/libScoutingAppEditor-ScoutingApp.dylib \
  --ignore-filename-regex "$TARGET/Engine" \
  --ignore-filename-regex "$TARGET/Content/ScoutingApp/Source/ScoutingApp/Private/Tests" \
  Content/ScoutingApp/Source
```

**Checkpoint:** TOTAL row shows ~68% region / ~80% line coverage. ~40 source files listed.

## CLI Reference

```
python3 -m laika_build_unreal.run_mac_coverage [test_names...] [options]

Positional:
  test_names              Automation test names or patterns (default: "All")

Options:
  --skip-build            Skip the UBT build step
  --include-tests         Include test source files in coverage
  --no-clean              Do not clean previous coverage outputs
  --configuration CONFIG  Build configuration (default: Development)
  --no-uba                Disable Unreal Build Accelerator
  --llvm-cov-tool PATH    Explicit path to llvm-cov
  --llvm-profdata-tool PATH  Explicit path to llvm-profdata
  --llvm-nm-tool PATH     Explicit path to llvm-nm
  --html-report-dir PATH  Override HTML report directory
  --lcov-output PATH      Override LCOV output path
  --summary-output PATH   Override summary output path
  --engine-root PATH      Override engine root path
  --uproject PATH         Override project file path
```

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success — all reports generated |
| 1 | Validity gate failed (no profiles, no binaries, zero coverage) |
| 2 | Setup error (missing tools, missing editor, wrong root) |
