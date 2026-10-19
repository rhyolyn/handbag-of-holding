# Automated Report Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate status-report (Tue/Thu), monthly, and annual report generation from work receipts in the worky Obsidian vault, scheduled via Windows Task Scheduler running Claude Code headless.

**Architecture:** Two single-purpose skills in `Agent/skills/` (`status-report-create`, `report-rollup`) do the report writing; a thin cross-platform Python runner in `Scripts/` invokes `claude -p` headless, logs, commits, and updates a visible status line. Reports are drafts until the user flips frontmatter to `final`.

**Tech Stack:** Claude Code skills (markdown), PowerShell 7, Windows Task Scheduler, git (local-only repo, already initialized), Obsidian Bases for the draft-review dashboard.

**Spec:** `C:\git\worky\Agent\docs\superpowers\specs\2026-07-11-automated-reports-design.md`

**Additional Requirements** check of each task as it's completed

## Global Constraints

- Vault root: `C:\git\worky` (home machine). Git repo already initialized there, no remote — do not add one. Obsidian Sync is the backup/distribution mechanism.
- `.gitignore` already contains `.obsidian/workspace*` and `Scripts/logs/` — do not duplicate entries.
- Status report template sections come verbatim from `C:\git\worky\Templates\Status Report Template.md`: Summary, Completed, In Progress, Leadership / Coordination, Next Steps / Upcoming, Risks / Blockers, Source Material (with subsections Status Report Candidates, Related Work Receipts).
- All generated reports carry `status: draft` frontmatter. Flipping to `final` is manual, always.
- Idempotency rule everywhere: skip generation if a report for the window already exists — never "did a task run today."
- Times are local Pacific ("6am my time", tracks PST/PDT). Task Scheduler local time handles this.
- Task Scheduler tasks get registered on **one machine only** (this one). Duplicate schedulers on synced machines would produce duplicate reports.
- New receipts filename convention: `WR-YYYY-MM-DD_<topic-slug>.md`, single `.md` extension.
- `Receipts/cost-ledger.csv` stays at that exact path; header: `date,topic_slug,model,input_tokens,cache_read_tokens,cache_write_tokens,output_tokens,total_usd`.
- Out of scope: cloud/CI execution, GitHub remote, rewriting existing status reports, back-filling historical windows, scheduling annual reports.

## Execution model guide (applies to every task)

Each task below has an **Execution recommendation** block naming a Claude model and a Codex configuration. Rationale conventions (established in `Receipts/WR-2026-07-11_ugs-plan-reviewing-model-recs.md`):

- File moves, git plumbing, config → Haiku 4.5 / Codex low reasoning. Cheap and sufficient.
- PowerShell scripts, scheduler registration, pattern-following skill authoring → Sonnet 4.6 / Codex medium.
- Novel skill design with date-window edge cases → Opus 4.8 / Codex high. Only Task 3 qualifies.
- If executing inline in one session, do not switch models mid-batch — the cache invalidation costs more than the tier savings. Pick the batch's highest-tier task and run the whole batch on it.

---

## Batch 1 — Foundation (Tasks 1–2)

Pure file operations and git. No skill-authoring context needed, so don't spend a frontier model or carry this context into Batch 2.

### Task 1: Baseline git commit of the vault

The repo exists at `C:\git\worky` with one commit (`faa2367`, the design spec) and everything else untracked. Establish the baseline so scheduled runs later commit only their own output.

**Files:**
- Modify: none (git state only)

**Interfaces:**
- Produces: a clean `git status` at `C:\git\worky`, which Task 5's wrapper commit logic depends on.

- [ ] **Step 1: Verify ignore rules work before committing**

Run: `git -C C:\git\worky status --porcelain | Select-String -Pattern "workspace|Scripts/logs"`
Expected: no output. If `.obsidian/workspace.json` or log files appear, stop and fix `C:\git\worky\.gitignore` first.

- [ ] **Step 2: Stage and commit everything**

```powershell
git -C C:\git\worky add -A
git -C C:\git\worky commit -m "Baseline vault snapshot before report automation"
```

- [ ] **Step 3: Verify clean tree**

Run: `git -C C:\git\worky status`
Expected: `nothing to commit, working tree clean`

**Execution recommendation:**
- **Claude:** Haiku 4.5 (`claude-haiku-4-5-20251001`) — mechanical git operations.
- **Codex:** default model, low reasoning effort.

### Task 2: Receipts migration + work-receipt-create skill update

Migrate flat `Receipts/` to `Receipts/YYYY/YYYY-MM/` (matching the Status Reports convention), fix `.md.md` double extensions, and point the `work-receipt-create` skill at the new layout. Multi-day receipts (`WR-A_to_B-slug`) file under their **end date** (`B`).

**Files:**
- Move: every `Receipts/WR-*.md*` file into `Receipts/YYYY/YYYY-MM/` derived from its end date
- Keep in place: `Receipts/cost-ledger.csv`
- Modify: `C:\git\worky\Agent\skills\work-receipt-create\SKILL.md` (File Output Target section)

**Interfaces:**
- Produces: `Receipts/YYYY/YYYY-MM/` layout that Task 3's receipt-collection logic globs against.

- [ ] **Step 1: Resolve the known duplicate before touching extensions**

`Receipts/WR-2026-05-28_to_2026-05-28-compare_troubleshooting_files.md` and `...files.md.md` both exist. Extension-fixing would collide.

```powershell
$a = "C:\git\worky\Receipts\WR-2026-05-28_to_2026-05-28-compare_troubleshooting_files.md"
$b = "$a.md"
if ((Get-FileHash $a).Hash -eq (Get-FileHash $b).Hash) { Remove-Item $b -Confirm:$false } else { Write-Host "CONTENTS DIFFER - diff manually, merge into $a, then delete $b" }
```

If contents differ, diff them, keep the superset in the `.md` file, delete the `.md.md` file.

- [ ] **Step 2: Migrate with a script (end-date extraction + extension fix)**

```powershell
Get-ChildItem C:\git\worky\Receipts -File -Filter "WR-*" | ForEach-Object {
    # end date = last YYYY-MM-DD in the filename (handles WR-A_to_B and WR-A_to-B typo forms)
    $dates = [regex]::Matches($_.Name, '\d{4}-\d{2}-\d{2}')
    if ($dates.Count -eq 0) { Write-Warning "SKIP (no date): $($_.Name)"; return }
    $end = $dates[$dates.Count - 1].Value
    $year = $end.Substring(0, 4); $month = $end.Substring(0, 7)
    $dest = "C:\git\worky\Receipts\$year\$month"
    New-Item -ItemType Directory -Force $dest | Out-Null
    $newName = $_.Name -replace '\.md\.md$', '.md'
    if (Test-Path (Join-Path $dest $newName)) { Write-Warning "COLLISION: $newName"; return }
    Move-Item $_.FullName (Join-Path $dest $newName)
}
```

- [ ] **Step 3: Verify migration is complete and lossless**

```powershell
Get-ChildItem C:\git\worky\Receipts -File | Where-Object Name -ne "cost-ledger.csv"   # expect: empty
Get-ChildItem C:\git\worky\Receipts -Recurse -File -Filter "*.md"                     # expect: empty
(Get-ChildItem C:\git\worky\Receipts -Recurse -File -Filter "WR-*").Count             # expect: 38 (39 originals minus 1 duplicate)
```

- [ ] **Step 4: Update the work-receipt-create skill's File Output Target**

In `C:\git\worky\Agent\skills\work-receipt-create\SKILL.md`, replace the first bullet of `## File Output Target` with:

```markdown
- Write the receipt to the current month's folder of the `worky` checkout this skill lives in: `<skill base dir>\..\..\..\Receipts\YYYY\YYYY-MM\` where `YYYY-MM` is the receipt's end date (the skill sits at `<worky root>\Agent\skills\work-receipt-create`). Create the month folder if it does not exist.
```

Leave the cost-ledger path references unchanged (`Receipts\cost-ledger.csv` is correct — it stays at the top level).

- [ ] **Step 5: Commit**

```powershell
git -C C:\git\worky add -A
git -C C:\git\worky commit -m "Migrate Receipts to YYYY/YYYY-MM layout, fix .md.md extensions, update work-receipt-create target"
```

**Execution recommendation:**
- **Claude:** Sonnet 4.6 (`claude-sonnet-4-6`) — mechanical moves, but end-date extraction and the duplicate/collision handling need care.
- **Codex:** default model, medium reasoning effort.

---

> **BATCH BOUNDARY — end of Batch 1.** Foundation is pure file ops; nothing from this session's context helps skill authoring. Start Batch 2 fresh with the handoff prompt below. (If running subagent-driven in one orchestrator session, this is a review checkpoint: verify Step 3 counts before dispatching Task 3.)

**Handoff prompt for Batch 2:**

```
Execute Batch 2 (Tasks 3-4) of the implementation plan at
C:\git\worky\Agent\docs\superpowers\plans\2026-07-11-automated-reports.md
using the superpowers:executing-plans skill (or dispatch per-task subagents via
superpowers:subagent-driven-development).

Context you need:
- Design spec: C:\git\worky\Agent\docs\superpowers\specs\2026-07-11-automated-reports-design.md
- Status report template: C:\git\worky\Templates\Status Report Template.md
- Receipts now live in C:\git\worky\Receipts\YYYY\YYYY-MM\ (migrated in Batch 1);
  cost ledger at C:\git\worky\Receipts\cost-ledger.csv
- Existing status reports: C:\git\worky\Status Reports\YYYY\YYYY-MM\
- Skills directory: C:\git\worky\Agent\skills\

Batch 1 (baseline git commit, receipts migration) is done - verify with
`git -C C:\git\worky log --oneline -3` before starting. Tasks 3 and 4 create the
status-report-create and report-rollup skills and verify each against real
historical receipts using the window overrides specified in the plan.
```

---

## Batch 2 — Report skills (Tasks 3–4)

Skill authoring plus verification against real historical receipts. These two tasks share context (template, frontmatter schema, window semantics) — run them in one session.

### Task 3: `status-report-create` skill

**Files:**
- Create: `C:\git\worky\Agent\skills\status-report-create\SKILL.md`
- Test output (manual run): `C:\git\worky\Status Reports\2026\2026-07\sr-2026-07-09.md`

**Interfaces:**
- Consumes: receipts at `Receipts/YYYY/YYYY-MM/WR-*.md` (Task 2 layout); template at `Templates/Status Report Template.md`.
- Produces: report files `Status Reports/YYYY/YYYY-MM/sr-YYYY-MM-DD.md` with frontmatter keys `status`, `window_start`, `window_end`, `sources`, `generated` — exactly the schema Task 4 reads. Invocable as `/status-report-create` and `/status-report-create window <start>..<end>`.

- [ ] **Step 1: Write the skill file**

Create `C:\git\worky\Agent\skills\status-report-create\SKILL.md` with exactly this content:

````markdown
---
name: status-report-create
description: Use when generating a Tue/Thu status report from work receipts, when a scheduled status-report run fires, or when the user invokes /status-report-create (optionally with an explicit window override like "window 2026-07-07..2026-07-09").
---

# Status Report Create

Generate one status report covering a Tue/Thu reporting window from work receipts. Runs headless on a schedule or on demand.

## Vault Layout

Resolve the vault root from this skill's base directory: `<skill base dir>\..\..\..` (the skill sits at `<worky root>\Agent\skills\status-report-create`).

- Receipts: `<vault>\Receipts\YYYY\YYYY-MM\WR-*.md`
- Reports out: `<vault>\Status Reports\YYYY\YYYY-MM\sr-YYYY-MM-DD.md`
- Template: `<vault>\Templates\Status Report Template.md`
- Cost ledger: `<vault>\Receipts\cost-ledger.csv`

## Window Computation

Report boundaries are Tuesdays and Thursdays at 06:00 local Pacific time.

1. **window_end** = the most recent Tue-or-Thu 06:00 boundary that is in the past (relative to now). Example: run on Thu 2026-07-16 at 06:05 → window_end is Thu 2026-07-16 06:00. Run on Wed → window_end is Tue 06:00.
2. **window_start** = the `window_end` frontmatter value of the most recent existing status report (newest `sr-*.md` by filename date under `Status Reports/`, reading its YAML frontmatter). Fallback if none exists or none has the frontmatter: the Tue-or-Thu 06:00 boundary immediately before window_end.
3. **Window override:** if invoked with `window <start>..<end>` (dates, e.g. `window 2026-07-07..2026-07-09`), use `<start>T06:00` and `<end>T06:00` local time verbatim and skip steps 1-2.
4. **Idempotency check:** the output filename is `sr-<window_end date as YYYY-MM-DD>.md`. If that file already exists in the target month folder, print "Report for window ending <date> already exists: <path> - skipping." and stop. Do not overwrite.

Deriving window_start from the last report (not from "today") makes catch-up runs correct after missed schedules and makes re-runs idempotent.

## Receipt Collection

A receipt belongs to the window if its **end date** is `>= window_start` and `< window_end`.

- End date = the **last** `YYYY-MM-DD` occurring in the filename. `WR-2026-04-17_to_2026-05-22-nfs_copy.md` ends 2026-05-22; `WR-2026-07-10_optitrack-p4-staging.md` ends 2026-07-10. Multi-day receipts belong to the window in which the work concluded.
- Receipt dates carry no time component; treat a receipt's end date as that day at 06:00 local for the boundary comparison (a receipt dated the same day as window_end is **inside** the window only if window_end's boundary comparison places 06:00 < 06:00 = false — i.e., it lands in the next window; a receipt dated the day of window_start at 06:00 is inside this window).
- Only scan the month folders that overlap the window (`Receipts/YYYY/YYYY-MM/` for each month touched by the window).

If no receipts fall in the window, still write the report: put "No receipts in window." as the sole Summary bullet and leave other sections as single `- None this period.` bullets. An empty period is information, not an error.

## Report Format

Write `Status Reports/YYYY/YYYY-MM/sr-YYYY-MM-DD.md` (create the month folder if needed) where the date is window_end's date, `YYYY`/`YYYY-MM` from window_end. Frontmatter first:

```yaml
---
status: draft
window_start: 2026-07-09T06:00-07:00
window_end: 2026-07-14T06:00-07:00
sources:
  - "[[WR-2026-07-10_optitrack-p4-staging]]"
generated: 2026-07-14T06:02-07:00
---
```

- `sources`: one wikilink per receipt in the window (filename without extension). Empty list if none.
- `generated`: current local timestamp with UTC offset. Use the correct Pacific offset for the date (-07:00 PDT, -08:00 PST).

Body uses exactly the template's sections and heading levels:

```markdown
# Status Report — YYYY-MM-DD

## Summary
## Completed
## In Progress
## Leadership / Coordination
## Next Steps / Upcoming
## Risks / Blockers
## Source Material
### Status Report Candidates
### Related Work Receipts
```

Fill sections from the receipts' content:

- **Summary**: 2-4 bullets of high-level impact and themes across the window's receipts.
- **Completed / In Progress**: derive from each receipt's Goal, Changes, and Handoff sections (a receipt with a non-N/A Handoff usually indicates in-progress work).
- **Leadership / Coordination**: from receipts' Coordination sections; `- None this period.` if all TBD.
- **Next Steps / Upcoming**: from Handoff sections.
- **Risks / Blockers**: from Risks / Unknowns sections; `- None this period.` if none.
- **Status Report Candidates**: each receipt's Suggested Status Bullet, verbatim.
- **Related Work Receipts**: wikilink list mirroring `sources`.

Keep bullets factual and concise. Do not invent work that is not in a receipt.

## Cost Ledger

After writing the report, append one row to `<vault>\Receipts\cost-ledger.csv`:
`date,topic_slug,model,input_tokens,cache_read_tokens,cache_write_tokens,output_tokens,total_usd` — use `sr-YYYY-MM-DD` as topic_slug and this session's model and token usage (estimate from session evidence if the transcript is unavailable; blank total_usd if no authoritative rate).

## Output

Print exactly: the report file path on one line, then `sources: N receipts`. In headless mode this is what the wrapper log captures.
````

- [ ] **Step 2: Verify skill is discoverable**

Run: `Get-ChildItem C:\git\worky\Agent\skills\status-report-create\SKILL.md`
Expected: file exists. (Skills in `Agent/skills/` are already symlinked into all harnesses per the spec.)

- [ ] **Step 3: Test with a historical window override against known receipts**

Run from `C:\git\worky`: `claude -p "/status-report-create window 2026-07-07..2026-07-09" --permission-mode acceptEdits`

Expected: creates `C:\git\worky\Status Reports\2026\2026-07\sr-2026-07-09.md` with `status: draft`, `window_start: 2026-07-07T06:00-07:00`, `window_end: 2026-07-09T06:00-07:00`, and `sources` containing exactly `[[WR-2026-07-07_vistest-ugs-pcb-consumer-missing-modules-handoff]]` (the only receipt whose end date falls in Tue 07-07 06:00 → Thu 07-09 06:00). Read the file and check all template sections are present.

- [ ] **Step 4: Test idempotency**

Re-run the same command.
Expected: output says the report already exists and skips; file's modification time is unchanged.

- [ ] **Step 5: Test the empty-window path**

Run: `claude -p "/status-report-create window 2026-06-16..2026-06-18" --permission-mode acceptEdits`
Expected: `Status Reports/2026/2026-06/sr-2026-06-18.md` exists with "No receipts in window." in Summary and an empty `sources:` list. Delete this test file afterward (it's a synthetic window, not a real reporting artifact): `Remove-Item "C:\git\worky\Status Reports\2026\2026-06\sr-2026-06-18.md" -Confirm:$false`

- [ ] **Step 6: Verify a cost-ledger row was appended**

Run: `Get-Content C:\git\worky\Receipts\cost-ledger.csv -Tail 3`
Expected: rows with `sr-2026-07-09` (and the test window) topic slugs.

- [ ] **Step 7: Commit**

```powershell
git -C C:\git\worky add "Agent/skills/status-report-create" "Status Reports/2026/2026-07/sr-2026-07-09.md" "Receipts/cost-ledger.csv"
git -C C:\git\worky commit -m "Add status-report-create skill, verified against 2026-07-07..09 window"
```

**Execution recommendation:**
- **Claude:** Opus 4.8 (`claude-opus-4-8`) — this is the plan's one genuinely novel task: window/boundary edge cases (catch-up, DST offsets, same-day receipts) are where a weaker model writes a subtly wrong skill that fails silently on a schedule.
- **Codex:** default model, high reasoning effort.

### Task 4: `report-rollup` skill

**Files:**
- Create: `C:\git\worky\Agent\skills\report-rollup\SKILL.md`
- Test output (manual run): `C:\git\worky\Status Reports\2026\2026-06\monthly-2026-06.md`

**Interfaces:**
- Consumes: status reports with the Task 3 frontmatter schema (`status`, `window_end`, `sources`).
- Produces: `Status Reports/YYYY/YYYY-MM/monthly-YYYY-MM.md` and `Reviews/annual-YYYY.md`. Invocable as `/report-rollup month YYYY-MM` and `/report-rollup year YYYY`.

- [ ] **Step 1: Write the skill file**

Create `C:\git\worky\Agent\skills\report-rollup\SKILL.md` with exactly this content:

````markdown
---
name: report-rollup
description: Use when rolling up status reports into a monthly report or an annual performance-review document, when a scheduled monthly-rollup run fires, or when the user invokes /report-rollup with "month YYYY-MM" or "year YYYY".
---

# Report Rollup

Roll status reports up into a monthly summary or an annual performance-review document.

## Vault Layout

Resolve the vault root from this skill's base directory: `<skill base dir>\..\..\..` (the skill sits at `<worky root>\Agent\skills\report-rollup`).

- Inputs: `<vault>\Status Reports\YYYY\YYYY-MM\sr-*.md` (only files with YAML frontmatter containing `window_end` — ignore legacy reports and Kindle notes without it)
- Monthly output: `<vault>\Status Reports\YYYY\YYYY-MM\monthly-YYYY-MM.md`
- Annual output: `<vault>\Reviews\annual-YYYY.md` (create `Reviews\` if needed)
- Cost ledger: `<vault>\Receipts\cost-ledger.csv`

## Arguments

Exactly one window argument, required:

- `month YYYY-MM` — window is the 1st of that month 00:00 local Pacific to the 1st of the next month 00:00 local Pacific. Audience: monthly summary for the user's own tracking and their manager.
- `year YYYY` — Jan 1 00:00 to next Jan 1 00:00 local Pacific. Audience: performance review — frame accomplishments as impact, scope, and growth narratives, not a chronological log.

If the argument is missing or malformed, print usage and stop; do not guess.

## Input Selection

A status report belongs to the window if its frontmatter `window_end` falls inside it. For `year`, monthly reports are preferred sources when they exist; fall back to the individual status reports of months with no monthly report.

**Idempotency:** if the output file already exists, print "Rollup for <window> already exists: <path> - skipping." and stop. Do not overwrite.

If zero source reports fall in the window, still write the output with "No status reports in window." as the body of the first section.

## Draft Flagging

Sources with `status: draft` are consumed normally but must be flagged. If any source is still a draft, put this callout immediately after the frontmatter:

```markdown
> [!warning] Unreviewed sources
> The following source reports were still `status: draft` at generation time:
> - [[sr-2026-06-04]]
> - [[monthly-2026-05]]
```

## Output Format

Frontmatter for both output types:

```yaml
---
status: draft
window: 2026-06            # or "2026" for annual
sources:
  - "[[sr-2026-06-04]]"
generated: 2026-07-01T06:07-07:00
---
```

**Monthly body** (`# Monthly Report — YYYY-MM`): sections `## Summary`, `## Completed`, `## In Progress`, `## Leadership / Coordination`, `## Risks / Blockers`, `## Source Reports`. Merge and deduplicate bullets across the month's status reports; collapse per-window minutiae into month-level themes. `## Source Reports` lists wikilinks to every consumed report.

**Annual body** (`# Annual Review Material — YYYY`): sections `## Year in Review` (3-5 sentence narrative), `## Major Accomplishments` (each with impact framing: what changed, for whom, at what scope), `## Technical Leadership`, `## Growth & Scope Changes`, `## Themes for Next Year`, `## Source Reports`. Write for a performance-review reader: impact over activity, outcomes over task lists.

## Cost Ledger

Append one row to `<vault>\Receipts\cost-ledger.csv` (same header as always) with topic_slug `monthly-YYYY-MM` or `annual-YYYY`.

## Output

Print exactly: the output file path on one line, then `sources: N reports (M drafts)`.
````

- [ ] **Step 2: Test the monthly rollup against June 2026**

Run from `C:\git\worky`: `claude -p "/report-rollup month 2026-06" --permission-mode acceptEdits`

Expected: creates `C:\git\worky\Status Reports\2026\2026-06\monthly-2026-06.md`. June's existing `sr-*.md` files predate the frontmatter schema, so the likely-correct outcome is "No status reports in window." — that verifies the frontmatter filter ignores legacy files rather than crashing on them. Read the output and confirm frontmatter + sections.

- [ ] **Step 3: Test idempotency and the malformed-argument path**

Re-run the same command. Expected: skip message, file unchanged.
Run: `claude -p "/report-rollup"` — Expected: usage message, no file written.

- [ ] **Step 4: Commit**

```powershell
git -C C:\git\worky add "Agent/skills/report-rollup" "Status Reports/2026/2026-06/monthly-2026-06.md" "Receipts/cost-ledger.csv"
git -C C:\git\worky commit -m "Add report-rollup skill, verified against month 2026-06"
```

**Execution recommendation:**
- **Claude:** Sonnet 4.6 (`claude-sonnet-4-6`) — follows the pattern Task 3 established; window logic here is simple calendar months.
- **Codex:** default model, medium reasoning effort.

---

> **BATCH BOUNDARY — end of Batch 2.** Skills are done and verified against historical data. Batch 3 is Windows automation (PowerShell + Task Scheduler + dashboards) — different domain, none of the skill-authoring context transfers. Start fresh with the handoff prompt below.

**Handoff prompt for Batch 3:**

```
Execute Batch 3 (Tasks 5-6) of the implementation plan at
C:\git\worky\Agent\docs\superpowers\plans\2026-07-11-automated-reports.md
using the superpowers:executing-plans skill (or dispatch per-task subagents via
superpowers:subagent-driven-development).

Context you need:
- Design spec: C:\git\worky\Agent\docs\superpowers\specs\2026-07-11-automated-reports-design.md
- Working skills (done in Batch 2): C:\git\worky\Agent\skills\status-report-create\SKILL.md
  and C:\git\worky\Agent\skills\report-rollup\SKILL.md - invoked headless as
  `claude -p "/status-report-create"` and `claude -p "/report-rollup month YYYY-MM"`
  from cwd C:\git\worky
- Scripts go in C:\git\worky\Scripts\ (exists, empty); logs in C:\git\worky\Scripts\logs\
  (gitignored already)
- Status dashboard to update: C:\git\worky\Dashboards\System Status.md
- Reports land in C:\git\worky\Status Reports\YYYY\YYYY-MM\

Verify Batch 2 completed with `git -C C:\git\worky log --oneline -3` (expect the two
skill commits). Tasks 5 and 6 write the Python report runner, register Task Scheduler
tasks (THIS machine only), and create the draft-review dashboard. This machine is the
single scheduler host - do not register tasks anywhere else.
```

---

## Batch 3 — Automation & visibility (Tasks 5–6)

### Task 5: Report runner (cross-platform Python)

One Python runner, parameterized by report type, so the same script drives both reports on any OS. Responsibilities: cwd to vault, run Claude headless, tee to log, detect success (the expected report file exists), commit on success, always update the System Status line. Standard library only (no third-party deps, no PowerShell) so it runs unchanged on Windows and Linux. Rationale for one script over two: the wrappers differed only in prompt and success check; a single runner keeps the shared git/logging/dashboard logic in one place (AGENTS.md: refactor duplication early).

**Files:**
- Create: `C:\git\worky\Scripts\run_report.py`
- Modify: `C:\git\worky\Dashboards\System Status.md` (add a `## Scheduled Runs` section the runner rewrites)

**Interfaces:**
- Consumes: `/status-report-create` and `/report-rollup month YYYY-MM` skill invocations (Batch 2).
- Produces: `python run_report.py {status|monthly} [--dry-run]`, exit code 0 on success / 1 on failure — the contract Task 6's scheduled tasks call.

- [ ] **Step 1: Seed the Scheduled Runs section in the dashboard**

Append to `C:\git\worky\Dashboards\System Status.md`:

```markdown

---

## Scheduled Runs
- status-report: never run
- monthly-rollup: never run
```

- [ ] **Step 2: Write `C:\git\worky\Scripts\run_report.py`**

One runner for both reports. Each report type is described by a small config (dashboard key, prompt, commit message, paths to stage, and a "did the expected output appear" check); the shared runner handles logging, success detection, the dashboard status line, and the commit. Standard-library only — `pathlib`, `subprocess`, `datetime`, `argparse` — so nothing is Windows-specific.

```python
"""Cross-platform runner for scheduled worky reports.

Invoked by the OS scheduler as:  python run_report.py {status|monthly} [--dry-run]

Runs the matching Claude Code skill headless, records the outcome on the System
Status dashboard, and commits generated output on success. Standard library only
so the same script runs unchanged on Windows and Linux.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
DASHBOARD = VAULT / "Dashboards" / "System Status.md"
LOG_DIR = VAULT / "Scripts" / "logs"


@dataclass(frozen=True)
class ReportType:
    task: str                       # dashboard line key, e.g. "status-report"
    prompt: str                     # prompt passed to `claude -p`
    commit_message: str
    stage_paths: tuple[str, ...]    # paths to `git add` on a real (non-dry-run) success
    produced_output: Callable[[], bool]  # True once the expected report file exists


def build_status_report() -> ReportType:
    reports = VAULT / "Status Reports"
    before = _count_reports(reports)
    return ReportType(
        task="status-report",
        prompt="/status-report-create",
        commit_message=f"Scheduled status report {date.today():%Y-%m-%d}",
        stage_paths=("Status Reports", "Receipts/cost-ledger.csv", "Dashboards/System Status.md"),
        produced_output=lambda: _count_reports(reports) > before,
    )


def build_monthly_rollup() -> ReportType:
    prev_month = _previous_month()
    expected = VAULT / "Status Reports" / prev_month[:4] / prev_month / f"monthly-{prev_month}.md"
    return ReportType(
        task="monthly-rollup",
        prompt=f"/report-rollup month {prev_month}",
        commit_message=f"Scheduled monthly rollup {prev_month}",
        stage_paths=("Status Reports", "Receipts/cost-ledger.csv"),
        produced_output=expected.exists,
    )


BUILDERS = {"status": build_status_report, "monthly": build_monthly_rollup}


def run(report: ReportType, dry_run: bool) -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{report.task}-{datetime.now():%Y-%m-%d-%H%M}.log"

    exit_code = _invoke_claude(report.prompt, log_path)
    skipped = _log_mentions(log_path, "already exists")

    # Success = claude exited 0 AND (the expected report appeared OR the log shows an idempotent skip).
    if exit_code != 0 or not (report.produced_output() or skipped):
        _update_status_line(report.task, f"FAILED (exit {exit_code}, see {log_path.name})")
        return 1
    if skipped:
        _update_status_line(report.task, "success (skipped - already up to date)")
        return 0
    if dry_run:
        _update_status_line(report.task, "success (dry-run, not committed)")
        return 0

    _commit(report)
    return 0


def _invoke_claude(prompt: str, log_path: Path) -> int:
    command = ["claude", "-p", prompt, "--permission-mode", "acceptEdits"]
    result = subprocess.run(command, cwd=VAULT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log_path.write_text(result.stdout, encoding="utf-8")  # tee: keep the log,
    sys.stdout.write(result.stdout)                        # and echo for interactive/dry runs.
    return result.returncode


def _commit(report: ReportType) -> None:
    _git("add", *report.stage_paths)
    _update_status_line(report.task, "success")
    _git("add", "Dashboards/System Status.md")
    _git("commit", "-m", report.commit_message)


def _update_status_line(task: str, result: str) -> None:
    stamp = f"{datetime.now():%Y-%m-%d %H:%M}"
    new_line = f"- {task}: last run {stamp}, result: {result}"
    content = DASHBOARD.read_text(encoding="utf-8")
    content = re.sub(rf"(?m)^- {re.escape(task)}:.*$", new_line, content)
    DASHBOARD.write_text(content, encoding="utf-8", newline="")


def _count_reports(root: Path) -> int:
    return sum(1 for _ in root.rglob("sr-*.md")) if root.exists() else 0


def _previous_month() -> str:
    last_month = date.today().replace(day=1) - timedelta(days=1)
    return f"{last_month:%Y-%m}"


def _log_mentions(log_path: Path, needle: str) -> bool:
    return needle in log_path.read_text(encoding="utf-8")


def _git(*args: str) -> None:
    subprocess.run(["git", "-C", str(VAULT), *args], check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a scheduled worky report.")
    parser.add_argument("report", choices=BUILDERS, help="Which report to generate.")
    parser.add_argument("--dry-run", action="store_true", help="Run the skill but skip the git commit.")
    args = parser.parse_args(argv)
    return run(BUILDERS[args.report](), args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
```

Before committing, run the Python quality gate (mypy, ruff check, ruff format --check) per `skills\python-quality-gate`.

- [ ] **Step 3: Dry-run test the status report**

Run: `python C:\git\worky\Scripts\run_report.py status --dry-run`

Expected: exit code 0; a log file appears in `C:\git\worky\Scripts\logs\`; the `Scheduled Runs` line in `Dashboards\System Status.md` updates. Because Task 3 already generated the current window's report, the likely path is "success (skipped - already up to date)" — that's a valid test of the skip branch. `git -C C:\git\worky status` shows no new commit.

- [ ] **Step 4: Dry-run test the monthly rollup**

Run: `python C:\git\worky\Scripts\run_report.py monthly --dry-run`
Expected: exit 0, skip branch (June rollup exists from Task 4), dashboard line updated, no commit.

- [ ] **Step 5: Commit**

```powershell
git -C C:\git\worky add Scripts "Dashboards/System Status.md"
git -C C:\git\worky commit -m "Add cross-platform Python report runner with logging, dashboard status, dry-run"
```

**Execution recommendation:**
- **Claude:** Sonnet 4.6 (`claude-sonnet-4-6`) — straightforward Python with a clear spec; the success-detection branch is the only subtle part.
- **Codex:** default model, medium reasoning effort.

### Task 6: Task Scheduler registration + draft-review dashboard

**Files:**
- Create: Task Scheduler tasks `worky-status-report`, `worky-monthly-rollup` (system state, not files)
- Create: `C:\git\worky\Dashboards\Draft Reports.base`

**Interfaces:**
- Consumes: the `run_report.py` runner from Task 5.
- Produces: the running system; the draft-review chore surface.

Windows Task Scheduler invokes the Python interpreter directly. Use the full interpreter path (find it with `(Get-Command python).Source`) rather than a bare `python`, because a scheduled task may run under an account whose `PATH` does not include Python; the examples below assume `python.exe` resolves and note the substitution. On Linux the equivalent trigger is a cron/systemd entry running the same `python .../run_report.py <type>` command line.

- [ ] **Step 1: Register the Tue/Thu status-report task**

```powershell
$python = (Get-Command python).Source   # full interpreter path; see note above
$action = New-ScheduledTaskAction -Execute $python -Argument "C:\git\worky\Scripts\run_report.py status" -WorkingDirectory "C:\git\worky"
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday,Thursday -At 6:00am
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName "worky-status-report" -Action $action -Trigger $trigger -Settings $settings -Description "Generate Tue/Thu status report from work receipts"
```

`-StartWhenAvailable` is the "run as soon as possible after a missed start" requirement. Trigger time is local, so it tracks PST/PDT automatically.

- [ ] **Step 2: Register the monthly rollup task**

`New-ScheduledTaskTrigger` has no day-of-month option, so register with `schtasks` and then patch on `StartWhenAvailable` via `Set-ScheduledTask`. `schtasks /TR` takes the whole command line as one string, so quote the interpreter path:

```powershell
$python = (Get-Command python).Source   # full interpreter path; see note above
schtasks /Create /TN "worky-monthly-rollup" /TR "`"$python`" C:\git\worky\Scripts\run_report.py monthly" /SC MONTHLY /D 1 /ST 06:05 /F
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Set-ScheduledTask -TaskName "worky-monthly-rollup" -Settings $settings
```

- [ ] **Step 3: Verify both tasks exist with correct triggers**

```powershell
Get-ScheduledTask worky-status-report, worky-monthly-rollup | Format-List TaskName, State
(Get-ScheduledTaskInfo worky-status-report).NextRunTime   # expect next Tue or Thu 6:00am
(Get-ScheduledTaskInfo worky-monthly-rollup).NextRunTime  # expect 1st of next month 6:05am
```

- [ ] **Step 4: End-to-end test — run the scheduled task manually**

```powershell
Start-ScheduledTask worky-status-report
# wait ~2 minutes, then:
(Get-ScheduledTaskInfo worky-status-report).LastTaskResult   # expect 0
Get-Content (Get-ChildItem C:\git\worky\Scripts\logs\status-report-*.log | Sort-Object LastWriteTime | Select-Object -Last 1)
```

Expected: LastTaskResult 0, log shows the skill ran (skip branch is fine), `Dashboards\System Status.md` Scheduled Runs line has a fresh timestamp. This proves the full chain: scheduler → python → claude headless → dashboard.

- [ ] **Step 5: Create the draft-review dashboard**

Create `C:\git\worky\Dashboards\Draft Reports.base`:

```yaml
filters:
  and:
    - status == "draft"
views:
  - type: table
    name: Draft reports awaiting review
    order:
      - file.name
      - window_end
      - generated
```

Open it in Obsidian and confirm it lists `sr-2026-07-09` and `monthly-2026-06` (the Batch 2 test outputs). If the Bases syntax has drifted in the installed Obsidian version, adjust the filter syntax in-app until the draft list renders — the requirement is "one dashboard listing every `status: draft` report," not this exact YAML.

- [ ] **Step 6: Commit and close out**

```powershell
git -C C:\git\worky add "Dashboards/Draft Reports.base" "Dashboards/System Status.md"
git -C C:\git\worky commit -m "Register report schedulers (this machine only), add draft-review dashboard"
```

Also tick `Report generation` under Phase 3 in `C:\git\worky\Dashboards\System Status.md` (`- [ ]` → `- [x]`) and include it in the commit.

**Execution recommendation:**
- **Claude:** Sonnet 4.6 (`claude-sonnet-4-6`) — Windows Task Scheduler has fiddly APIs; Sonnet handles the documented fallback path fine. Prefer Claude Code over Codex here: the verification steps need interactive iteration against live scheduler state.
- **Codex:** default model, medium reasoning effort (workable, but second choice for this task).

---

> **BATCH BOUNDARY — end of Batch 3 / plan complete.** Remaining verification is calendar-driven, not agent-driven.

**Handoff prompt (final verification, next Tue/Thu after scheduled runs fire):**

```
The automated report system in C:\git\worky is fully installed (plan:
C:\git\worky\Agent\docs\superpowers\plans\2026-07-11-automated-reports.md, all 6 tasks
committed). Verify the first real scheduled cycle:

1. Check C:\git\worky\Dashboards\System Status.md "Scheduled Runs" - both lines
   should show recent timestamps and "success".
2. Check the newest report in C:\git\worky\Status Reports\2026\2026-07\ - frontmatter
   window_start must equal the previous report's window_end (no gap, no overlap).
3. Check `git -C C:\git\worky log --oneline -5` for the scheduled commits.
4. Check C:\git\worky\Scripts\logs\ for the run logs; investigate any FAILED status
   line via its log file.
5. If a run failed, re-running is safe: idempotency is keyed on "does a report for
   this window exist", so just fix the cause and run
   python C:\git\worky\Scripts\run_report.py status manually.

Trust the system only after one full cycle: a Tuesday run, a Thursday run, and (at the
next month boundary) a monthly rollup.
```

---

## Batch summary (context/cost rationale)

| Batch | Tasks | Session model | Why the boundary is here |
|---|---|---|---|
| 1 | 1–2 | Sonnet 4.6 (Task 2 sets the tier) | File ops + git; none of this context helps later batches. Cheap session, keep it short. |
| 2 | 3–4 | Opus 4.8 (Task 3 sets the tier) | Both skills share template/frontmatter/window context — splitting them would re-pay that context. Ends when skill authoring ends. |
| 3 | 5–6 | Sonnet 4.6 | Windows automation domain; wrapper + scheduler share the invocation contract. No skill-authoring context needed. |

Running all six tasks in one session would carry Batch 1's migration noise and Batch 2's full skill texts into Batch 3's scheduler work — paying cache-read on every turn for context the task doesn't use, and pinning the whole run to Opus pricing. Three sessions keep each context lean and let two of three batches run on Sonnet.
