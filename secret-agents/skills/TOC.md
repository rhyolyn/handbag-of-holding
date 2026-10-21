# Skills

Generated 2026-10-20. Run `/<canonical-name>`.

## Agent Workflow

Planning and execution workflows for agents.

### Agent Workflow (a)

- /agent-plan: Use when creating or revising an implementation plan that may span agents or sessions and needs explicit model routing, context-efficient batches, copy/paste handoffs, or durable progress tracking.

### Preflight (p)

- /ready-player-one: Run before executing a batched prompt or complex task. Verifies skill visibility, harness permissions, uv health, and no locked build artifacts. Autofixes safe issues; outputs 'ready' or a NOT READY list with exact remediation steps. Use when the user invokes /ready-player-one or @skill ready-player-one.

## Code Quality

Architecture, error-handling, testing, and quality-gate workflows.

### Code Quality (c)

- /clean-code-architecture-guards: Use when establishing an architectural rule that must survive future sessions - layer boundaries, import direction, state ownership, size tripwires - or when such a rule exists only in prose, review feedback, or comments and has no failing check in CI.
- /clean-code-error-handling: Use when designing or changing error handling, or when a repository has inline messages, generic exceptions, duplicate logging, string-parsed failures, scattered error types, or unclear error ownership.
- /python-quality-gate: Use before committing any Python change, after implementing or fixing Python code, or as the final check before opening a PR in a Python repository.

### Testing (t)

- /python-tdd-cycle: Use when implementing any new feature or fix in a Python project that uses pytest. Enforces the red-green loop: write failing tests first, confirm they fail, implement, confirm they pass, then run the full suite before committing.
- /run-unit-tests: Run a Python project's unit tests in a managed .venv. Creates the venv if missing, installs all test + pre-commit requirements (pytest, pre-commit, ruff, mypy, etc.), runs the full test suite and pre-commit, and (with --fix) repairs any failing tests or pre-commit violations. Use when the user asks to run unit tests, run the test suite, run pytest, check pre-commit, or says 'rut'.

## Maintenance

Library and model-maintenance workflows.

### Maintenance (m)

- /update-claude-pricing-doc: Use when the user asks to refresh or update Claude API pricing, or when claude-pricing.json is stale (>1 week old). WebFetches the official Anthropic pricing docs page, extracts only per-model token rates, and writes them to output/claude-pricing.json. Cheap and context-light; never invokes the claude-api skill.
- /update-model-routing: Use when model-routing.json may be stale, exact Codex or Claude model IDs need verification, or a plan needs current model profiles.

## Skill Authoring

Creating, discovering, installing, and maintaining skills.

### Query & Discovery (q)

- /query-all-skills: List canonical skills published in the shared catalog.

### Skill Management (s)

- /install-skills: Install catalog-published skills into harness mixing directories.
- /update-skill: Revise one canonical skill and republish its catalog-owned artifacts.
- /update-skills-readme: Regenerate and verify the canonical skills README and HTML guide.
- /write-skill: Create a canonical skill in a declared collection and publish it through the catalog.

## Unreal

Unreal Engine build, coverage, and release workflows.

### Testing (t)

- /run-mac-coverage: Use when running, validating, or debugging Scout Mac LLVM code coverage on a Mac test runner. Covers getting/installing the latest laika-build-unreal, running the coverage pipeline, verifying generated reports (HTML, LCOV, text, summary), and troubleshooting common failures.

### Unreal (u)

- /unreal-reset-build-env: Use when Unreal Engine builds, UGS builds, UBT/UAT/Build.bat/RunUAT.bat/GenerateProjectFiles, UBA, MSBuild, or Visual Studio shell state must be stopped or cleaned before starting a fresh Unreal build on Windows.
- /unreal-ugs-release: Use when building, validating, submitting, troubleshooting, or updating UnrealGameSync UGS precompiled editor binaries, PCB archives, BuildGraph Submit To Perforce For UGS flows, no-submit validation, shader worker mismatches, or UGS archive runbooks.

## Work Tracking

Check-in, Jira, reporting, and work-receipt workflows.

### Jira (j)

- /jira-human-ticket-create: Use when creating Jira tickets intended for human developers, especially when the request includes a title and partial technical context and needs a structured template with minimal follow-up questions.

### Reporting (r)

- /daily-note-create: Use when the user asks to create or normalize a daily work-context note for a local Pacific date.
- /git-receipt-create: Use when the user asks to record one merged GitHub pull request, standalone commit, or submitted review as work evidence.
- /git-receipt-range: Use when the user asks to backfill GitHub work evidence for a date range.
- /git-rollup: Use when the user asks to summarize GitHub source-control receipts by initiative for a reporting window.
- /perforce-receipt-create: Use when the user asks to record one Perforce changelist, or explicitly invokes @skill perforce-receipt-create with a CL number. Examines the changelist's description, file list, and diffs and writes a source-control receipt.
- /perforce-receipt-range: Use when the user asks to backfill Perforce source-control receipts for a date range, or explicitly invokes @skill perforce-receipt-range with start and end dates.
- /perforce-rollup: Use when the user asks to summarize Perforce source-control receipts over a bi-weekly, monthly, or custom window, or explicitly invokes @skill perforce-rollup with a cadence argument.
- /report-cost-analysis: Use when a work receipt needs optional AI token and cost analysis or an efficiency improvement plan, including after report-receipt --show-cost.
- /report-rollup: Use when the user asks to create a monthly or living annual report from combined work evidence.
- /report-status: Use when the user asks for a biweekly or custom status report synthesized from configured work evidence.
- /report-receipt: Use when the user asks to create or update a work receipt, WR, handoff note, status receipt, completion receipt, progress receipt, or explicitly invokes @skill report-receipt; especially when saving analysis, summarizing engineering work, or preserving text verbatim in a receipt.
