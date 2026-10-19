# Automated Report Generation — Design

**Date:** 2026-07-11
**Status:** Approved (pending user review of this written spec)

## Problem

The worky Obsidian vault tracks work via receipts in `Receipts/`, but status reports, monthly reports, and annual review material are assembled by hand. Automate generation:

1. **Status reports** every Tuesday and Thursday at 6am Pacific:
   - Tuesday: covers receipts from previous Thursday 6am → current Tuesday 6am.
   - Thursday: covers receipts from previous Tuesday 6am → current Thursday 6am.
2. **Monthly reports** from status reports, 1st of month 12am Pacific → 1st of next month 12am Pacific.
3. **Annual reports** on demand, framed for performance reviews.

## Decisions (settled during brainstorming)

- **Execution:** local Windows Task Scheduler running Claude Code headless (`claude -p`). No cloud agents, no CI.
- **Git:** the vault becomes its own local-only git repo (`git init` in `c:\git\worky`). No remote; Obsidian Sync remains the distribution/backup mechanism. This also untangles the vault from the accidental `C:\git`-level repo whose remote points at `qtpractice.git`.
- **Review flow:** generated reports are **drafts** (`status: draft` frontmatter) until the user flips them to `final`. Rollups consume drafts but flag unreviewed sources.
- **Skill structure:** two skills, not three (approach B below).

## Approach

Two single-purpose skills in `Agent/skills/` (already symlinked into all harnesses):

### Skill 1: `status-report-create`

- Computes the reporting window: from the `window_end` of the most recent existing status report (fallback: previous Tue/Thu 6am) to the nearest past Tue/Thu 6am boundary. Deriving the window from the last report — not from "today" — makes catch-up runs correct and re-runs idempotent (skip if a report for the window already exists).
- Collects receipts from `Receipts/YYYY/YYYY-MM/` whose **end date** falls inside the window. Multi-day receipts (`WR-A_to_B`) belong to the window in which the work concluded.
- Writes `Status Reports/YYYY/YYYY-MM/sr-YYYY-MM-DD.md` using `Templates/Status Report Template.md.md` sections, with frontmatter:

  ```yaml
  status: draft
  window_start: 2026-07-09T06:00-07:00
  window_end: 2026-07-14T06:00-07:00
  sources:
    - "[[WR-2026-07-10_optitrack-p4-staging]]"
  generated: 2026-07-14T06:02-07:00
  ```

- Appends its run cost to `Receipts/cost-ledger.csv`.

### Skill 2: `report-rollup`

- Takes a window argument (`month 2026-06` or `year 2026`) and an audience framing (monthly summary vs. performance review).
- Consumes status reports whose `window_end` falls in the window; lists any still-`draft` sources in a "Unreviewed sources" callout.
- Monthly output: `Status Reports/YYYY/YYYY-MM/monthly-YYYY-MM.md`, `status: draft`.
- Annual output: `Reviews/annual-YYYY.md`, on-demand only (never scheduled).
- Same idempotency rule (skip if output for the window exists) and cost-ledger append.

### Scheduling

- One cross-platform Python runner, `Scripts/run_report.py`, invoked with the report type as an argument (`status`, `monthly`) so the scheduler on any OS calls the same script. Rationale: the wrappers differed only in the `claude -p` prompt and target paths; a single parameterized runner avoids the duplicated shell logic (git add/commit, logging, dashboard update) that two near-identical scripts would carry. Standard library only — no PowerShell, no third-party deps — so it runs unchanged on Windows and Linux.
  - Set cwd to the vault root (resolved relative to the script location, not the caller's cwd) and invoke Claude Code headless via `subprocess.run(["claude", "-p", prompt])`; the monthly runner computes `<prev-month>` and builds `/report-rollup month <prev-month>`.
  - Write output to `Scripts/logs/<task>-<date>.log` using `pathlib.Path` and portable path joins (never hardcoded `\`).
  - On success: `git add` the generated report + ledger, then commit.
  - On any outcome (success or failure): update a status line in `Dashboards/System Status.md` (last run, result) so silent failures stay visible. Failures are logged once at the failure site and surfaced through the dashboard channel rather than swallowed.
  - Exit non-zero on failure so the scheduler records the run as failed.
- Scheduler tasks (registered on **one machine only** — Obsidian Sync spans machines, duplicate schedulers would produce duplicate reports):
  - Windows Task Scheduler runs `python <vault>\Scripts\run_report.py status` (or `monthly`); on Linux the same command line is driven by cron/systemd if automation moves there later.
  - Tue 6:00am local, Thu 6:00am local → `run_report.py status`.
  - 1st of month 6:05am local → `run_report.py monthly` (for the just-ended month).
  - All Windows tasks: "Run task as soon as possible after a scheduled start is missed" enabled.
- Times are **local Pacific** (tracks PST/PDT), interpreted as "6am my time" rather than fixed UTC-8.

### Receipts reorganization

- Migrate flat `Receipts/` to `Receipts/YYYY/YYYY-MM/`, matching the existing Status Reports convention. Multi-day receipts file under their end date.
- Fix `.md.md` double extensions during migration.
- `cost-ledger.csv` stays at `Receipts/cost-ledger.csv`.
- Update `work-receipt-create` skill to write new receipts into the current month's folder.
- Obsidian wikilinks (`[[name]]`) are path-independent, so moves don't break links; any markdown-style relative links would need checking (none expected).

### Git setup

- `git init` in `c:\git\worky`; nested inside the `C:\git` repo is fine (inner repo takes precedence).
- `.gitignore`: `.obsidian/workspace*`, `Scripts/logs/`.
- Baseline commit of the vault, then scheduled runs commit their own output.

### No MCP

The vault is plain markdown on disk; Claude Code's file tools read and write it directly. Obsidian MCP would only matter for live-app interaction (open panes, graph), which no report needs. Obsidian picks up new files via sync/vault watching.

## Error handling

- Skill can't find receipts in window → still writes the report with an explicit "No receipts in window" body (an empty period is information, not an error).
- Wrapper exit code nonzero or no new report file produced → log retained, System Status dashboard line marked failed, no commit.
- Re-run after failure is safe: idempotency check is "does a report for this window exist," not "did a task run today."

## Testing

- Skills are runnable on demand with an explicit window override (e.g. `/status-report-create window 2026-07-07..2026-07-09`) so behavior is verifiable against known historical receipts before any schedule exists.
- Dry-run flag on wrappers: run Claude, write the report, skip the commit.
- Verify one full scheduled cycle (Tue + Thu + month boundary) before trusting it; System Status dashboard is the check-in point.

## Out of scope

- Cloud/CI execution, GitHub remote (revisit later if wanted; local git makes it a one-command upgrade).
- Rewriting existing status reports or back-filling historical windows.
- Annual report scheduling (explicitly on-demand).

## Draft review loop

A Dashboards note (Obsidian Bases or Dataview) lists all reports with `status: draft`, making review-and-flip-to-final a visible chore. Flipping to `final` is manual and stays manual.
