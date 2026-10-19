# Scout Project Guidance

Project-specific guidance migrated from Worky Agent on 2026-10-13. Apply only to the Scout repository.

## Builder commands

- Prefer Builder scripts over direct Unreal tooling: from `d:\p4\ss` run `python root/builder/src/<script>.py`; from `d:\p4\ss\root` run `python builder/src/<script>.py`.
- Build: `build_game.py`. Project files: `generate_project_files.py --repo-root root`. All automation tests: `run_automation_tests.py --repo-root root`; focused runs append test names/prefixes (e.g. `Scout.AssetTracker`).
- Builder finds the repo root via `UnrealPathFinder`; default logs land in `<repo-root>/scout_logs`.
- "Live Coding active" reported after Unreal is closed: check for stale editor processes before retrying.

## Guard and logging macros

- Prefer the repo guard/logging macros (`RETURN_FALSE_IF`, `RETURN_FALSE_QUIETLY_IF`, `RETURN_IF_FALSE`, `RETURN_QUIETLY_IF`, `CONTINUE_IF`, `CONTINUE_QUIETLY_IF`) over 5+ line if/log/return blocks. Log at the lowest level with enough context to diagnose, then propagate silently through callers via quiet guards — one error, logged once (expected-failure tier only; see Error Handling).
