# Handbag of Holding Agent Skills

This guide inventories the 25 canonical workflows in the shared skills
library. Canonical sources live in manifest-declared collections; the catalog
publishes installable adapters under `_generated`. Read the root
[README](../README.md), then the applicable collection README and canonical
`SKILL.md` before changing any workflow.

The [catalog](catalog.json) and [TOC](TOC.md) are catalog-owned. This Markdown
file is rendered to [README.html](README.html); do not edit that HTML directly.

## How skills are wired and invoked

Use each workflow by its canonical name. The installer reads `catalog.json`
and links the matching `_generated/<canonical-name>` adapter into a harness
mixing directory. An adapter forwards to the single authored source, so a
workflow has one instruction owner.

To publish source changes, run the catalog update and check commands from the
root README, then render this guide. A collection README explains its boundary;
`collections.json` remains the machine-readable authority for collection names
and ordering.

## Skill inventory

| Skill | Canonical source | Purpose |
| --- | --- | --- |
| [agent-plan](#agent-plan) | [agent-workflow/agent-plan](agent-workflow/agent-plan/SKILL.md) | Creates or revises durable implementation plans. |
| [ready-player-one](#ready-player-one) | [agent-workflow/ready-player-one](agent-workflow/ready-player-one/SKILL.md) | Preflights complex or batched work. |
| [clean-code-architecture-guards](#clean-code-architecture-guards) | [code-quality/clean-code-architecture-guards](code-quality/clean-code-architecture-guards/SKILL.md) | Establishes enforceable architecture boundaries. |
| [clean-code-error-handling](#clean-code-error-handling) | [code-quality/clean-code-error-handling](code-quality/clean-code-error-handling/SKILL.md) | Designs and repairs error-handling contracts. |
| [python-quality-gate](#python-quality-gate) | [code-quality/python-quality-gate](code-quality/python-quality-gate/SKILL.md) | Runs Python quality verification. |
| [python-tdd-cycle](#python-tdd-cycle) | [code-quality/python-tdd-cycle](code-quality/python-tdd-cycle/SKILL.md) | Enforces test-first Python changes. |
| [run-unit-tests](#run-unit-tests) | [code-quality/run-unit-tests](code-quality/run-unit-tests/SKILL.md) | Runs managed Python unit tests. |
| [update-claude-pricing-doc](#update-claude-pricing-doc) | [maintenance/update-claude-pricing-doc](maintenance/update-claude-pricing-doc/SKILL.md) | Refreshes Claude pricing data. |
| [update-model-routing](#update-model-routing) | [maintenance/update-model-routing](maintenance/update-model-routing/SKILL.md) | Refreshes model-routing data. |
| [query-all-skills](#query-all-skills) | [skill-authoring/query-all-skills](skill-authoring/query-all-skills/SKILL.md) | Finds available workflows. |
| [install-skills](#install-skills) | [skill-authoring/install-skills](skill-authoring/install-skills/SKILL.md) | Installs projection adapters into harnesses. |
| [update-skill](#update-skill) | [skill-authoring/update-skill](skill-authoring/update-skill/SKILL.md) | Revises a canonical workflow. |
| [update-skills-readme](#update-skills-readme) | [skill-authoring/update-skills-readme](skill-authoring/update-skills-readme/SKILL.md) | Updates this guide and its HTML rendering. |
| [write-skill](#write-skill) | [skill-authoring/write-skill](skill-authoring/write-skill/SKILL.md) | Authors a new canonical workflow. |
| [run-mac-coverage](#run-mac-coverage) | [unreal/run-mac-coverage](unreal/run-mac-coverage/SKILL.md) | Runs Scout Mac LLVM coverage. |
| [unreal-reset-build-env](#unreal-reset-build-env) | [unreal/unreal-reset-build-env](unreal/unreal-reset-build-env/SKILL.md) | Resets an Unreal build environment. |
| [unreal-ugs-release](#unreal-ugs-release) | [unreal/unreal-ugs-release](unreal/unreal-ugs-release/SKILL.md) | Builds and validates UGS release artifacts. |
| [jira-human-ticket-create](#jira-human-ticket-create) | [work-tracking/jira-human-ticket-create](work-tracking/jira-human-ticket-create/SKILL.md) | Creates developer-facing Jira tickets. |
| [checkin-receipt-create](#checkin-receipt-create) | [work-tracking/checkin-receipt-create](work-tracking/checkin-receipt-create/SKILL.md) | Creates one Perforce check-in receipt. |
| [checkin-receipt-range](#checkin-receipt-range) | [work-tracking/checkin-receipt-range](work-tracking/checkin-receipt-range/SKILL.md) | Backfills check-in receipts for a date range. |
| [checkin-rollup](#checkin-rollup) | [work-tracking/checkin-rollup](work-tracking/checkin-rollup/SKILL.md) | Summarizes check-in receipts. |
| [report-cost-analysis](#report-cost-analysis) | [work-tracking/report-cost-analysis](work-tracking/report-cost-analysis/SKILL.md) | Analyzes work-receipt AI costs. |
| [report-rollup](#report-rollup) | [work-tracking/report-rollup](work-tracking/report-rollup/SKILL.md) | Rolls status reports into a longer window. |
| [report-status](#report-status) | [work-tracking/report-status](work-tracking/report-status/SKILL.md) | Creates a current status report. |
| [report-receipt](#report-receipt) | [work-tracking/report-receipt](work-tracking/report-receipt/SKILL.md) | Creates or updates a work receipt. |

### agent-plan

Creates or revises a durable implementation plan. Read its canonical source in
the Agent Workflow collection.

### ready-player-one

Preflights a complex or batched task before execution.

### clean-code-architecture-guards

Establishes architecture rules together with enforceable checks.

### clean-code-error-handling

Designs error-handling boundaries and failure ownership.

### python-quality-gate

Runs the Python quality gate before integration work.

### python-tdd-cycle

Guides test-first implementation in Python projects.

### run-unit-tests

Runs a repository's managed Python unit-test workflow.

### update-claude-pricing-doc

Refreshes the maintained Claude pricing-data artifact.

### update-model-routing

Refreshes and validates model-routing data.

### query-all-skills

Lists the canonical workflows published in the catalog.

### install-skills

Links catalog projection adapters into selected harness directories.

### update-skill

Revises one canonical source and republishes its derived artifacts.

### update-skills-readme

Maintains this Markdown guide and renders its HTML output.

### write-skill

Creates a new canonical source in a declared collection.

### run-mac-coverage

Runs and diagnoses Scout Mac LLVM coverage.

### unreal-reset-build-env

Stops scoped Unreal build state before a fresh build.

### unreal-ugs-release

Builds, validates, and releases UGS precompiled-editor artifacts.

### jira-human-ticket-create

Creates a structured Jira ticket for human developers.

### checkin-receipt-create

Creates a receipt for one Perforce changelist.

### checkin-receipt-range

Creates receipts for every changelist in a requested range.

### checkin-rollup

Rolls check-in receipts into an initiative-oriented summary.

### report-cost-analysis

Analyzes optional AI token and cost information for work receipts.

### report-rollup

Combines status reports into a monthly, annual, or custom rollup.

### report-status

Creates a scheduled or explicitly-windowed status report.

### report-receipt

Creates or updates a durable engineering-work receipt.

## Maintaining this document

Run `update-skills-readme` after the catalog is current. The renderer verifies
every canonical catalog name has an inventory link and section, and refuses a
manifest/catalog mismatch before replacing `README.html`.
