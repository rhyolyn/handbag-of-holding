# Skills

Generated 2026-10-12. Run `/<short>` or `/<canonical-name>`.

## Agent Workflow (a)

- Smart Plan (`ap`) — Use when creating or revising an implementation plan that may span agents or sessions and needs explicit model routing, context-efficient batches, copy/paste handoffs, or durable progress tracking.

## Code Quality (c)

- Architecture Guards (`ccag`) — Use when establishing an architectural rule that must survive future sessions — layer boundaries, import direction, state ownership, size tripwires — or when such a rule exists only in prose, review feedback, or comments and has no failing check in CI. · Aliases: architecture-guards
- Clean Code: Error Handling (`cceh`) — Use when designing or changing error handling, or when a repository has inline messages, generic exceptions, duplicate logging, string-parsed failures, scattered error types, or unclear error ownership.
- Python Quality Gate (`cpqg`) — Use before committing any Python change, after implementing or fixing Python code, or as the final check before opening a PR in a Python repository.

## Jira (j)

- Jira Human Ticket Create (`jhtc`) — Use when creating Jira tickets intended for human developers, especially when the request includes a title and partial technical context and needs a structured template with minimal follow-up questions. · Aliases: jira-ht

## Maintenance (m)

- Update Claude Pricing Doc Skill (`mucpd`) — Use when the user asks to refresh or update Claude API pricing, or when claude-pricing.json is stale (>1 week old). WebFetches the official Anthropic pricing docs page, extracts only per-model token rates, and writes them to output/claude-pricing.json. Cheap and context-light; never invokes the claude-api skill.
- Update Model Routing (`mumr`) — Use when model-routing.json may be stale, exact Codex or Claude model IDs need verification, or a plan needs current model profiles.

## Preflight (p)

- Ready Player One (`prpo`) — Run before executing a batched prompt or complex task. Verifies skill visibility, harness permissions, uv health, and no locked build artifacts. Autofixes safe issues; outputs 'ready' or a NOT READY list with exact remediation steps. Use when the user invokes /ready-player-one or @skill ready-player-one. · Aliases: agent-preflight

## Query & Discovery (q)

- Query All Skills (`qas`) — Use when the user asks what skills are available, which agents or slash commands are loaded, or wants a summary of what each skill does.

## Reporting (r)

- Report Rollup (`rrol`) — Use when rolling up status reports into a monthly report or an annual performance-review document, when a scheduled monthly-rollup run fires, or when the user invokes /report-rollup with "month YYYY-MM" or "year YYYY".
- Status Report Create (`rs`) — Use when generating a Tue/Thu status report from work receipts, when a scheduled status-report run fires, or when the user invokes /report-status (optionally with an explicit window override like "window 2026-07-07..2026-07-09"). · Aliases: status-report-create
- Work Receipt Skill (`rrec`) — Use when the user asks to create or update a work receipt, WR, handoff note, status receipt, completion receipt, progress receipt, or explicitly invokes @skill report-receipt; especially when saving analysis, summarizing engineering work, or preserving text verbatim in a receipt. · Aliases: work-receipt-create

## Skill Management (s)

- Install Skills (`sis`) — Install agent skills into harness discovery locations by creating junctions (Windows) or symlinks (Mac/Linux). Use when adding skills to a new machine, a new harness location, or refreshing after skills have been added or removed.
- Update Skills README (`susr`) — Use when a skill under Agent/skills is added, removed, or edited, when the skills README.md or README.html is missing or stale, or when the user invokes /update-skills-readme (optionally with "review").

## Testing (t)

- Python TDD Cycle (`tptc`) — Use when implementing any new feature or fix in a Python project that uses pytest. Enforces the red-green loop: write failing tests first, confirm they fail, implement, confirm they pass, then run the full suite before committing.
- Run Mac Coverage (`trmc`) — Use when running, validating, or debugging Scout Mac LLVM code coverage on a Mac test runner. Covers getting/installing the latest laika-build-unreal, running the coverage pipeline, verifying generated reports (HTML, LCOV, text, summary), and troubleshooting common failures.
- Run Unit Tests (`trut`) — Run a Python project's unit tests in a managed .venv. Creates the venv if missing, installs all test + pre-commit requirements (pytest, pre-commit, ruff, mypy, etc.), runs the full test suite and pre-commit, and (with --fix) repairs any failing tests or pre-commit violations. Use when the user asks to run unit tests, run the test suite, run pytest, check pre-commit, or says 'rut'. · Aliases: rut

## Unreal (u)

- Reset Unreal Build Environment (`urbe`) — Use when Unreal Engine builds, UGS builds, UBT/UAT/Build.bat/RunUAT.bat/GenerateProjectFiles, UBA, MSBuild, or Visual Studio shell state must be stopped or cleaned before starting a fresh Unreal build on Windows. · Aliases: reset-unreal-build-environment
- UGS PCB Release (`uur`) — Use when building, validating, submitting, troubleshooting, or updating UnrealGameSync UGS precompiled editor binaries, PCB archives, BuildGraph Submit To Perforce For UGS flows, no-submit validation, shader worker mismatches, or UGS archive runbooks. · Aliases: ugs-pcb-release
