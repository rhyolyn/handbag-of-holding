---
name: report-rollup
description: Use when rolling up status reports into a monthly report or an annual performance-review document, when a scheduled monthly-rollup run fires, or when the user invokes /report-rollup with "month YYYY-MM" or "year YYYY".
---

# Report Rollup

**Category:** Reporting · **Updated:** 2026-10-16

Roll status reports into a monthly summary, or Perforce monthly checkin rollups into a living annual performance-review document.

## Vault Layout

Resolve `<vault>` using [Worky data vault paths](../../../runbooks/worky-vault-paths.md) before reading inputs or creating outputs.

- Inputs (monthly only): `<vault>\Status Reports\YYYY\YYYY-MM\sr-*.md` (only files with YAML frontmatter containing `window_end` — ignore legacy reports and Kindle notes without it)
- Checkin inputs (annual only): `<vault>\Checkins\perforce\YYYY\YYYY-MM\rollups\ck-monthly-YYYY-MM.md` — the monthly Perforce checkin rollups for the year. This is the complete evidence base for the annual review: every month that has a rollup in the year dir is consumed. Individual `CK-*.md` receipts are already summarized by their monthly rollup and are not consumed directly.
- Monthly output: `<vault>\Status Reports\YYYY\YYYY-MM\monthly-YYYY-MM.md`
- Annual output: `<vault>\Reviews\Performance\YYYY\perforce-annual-YYYY.md` (create `Reviews\Performance\YYYY\` if needed)
- Cost ledger: `<vault>\Receipts\cost-ledger.csv`

## Arguments

Exactly one window argument, required:

- `month YYYY-MM` — window is the 1st of that month 00:00 local Pacific to the 1st of the next month 00:00 local Pacific. Audience: monthly summary for the user's own tracking and their manager.
- `year YYYY` — everything available in the Perforce year dir for that year (Jan 1 through present if YYYY is the current year; the full year if YYYY is past). Audience: performance review — frame accomplishments as impact, scope, and growth narratives, not a chronological log.
- `year YYYY evidence combined` — preserve the original combined-evidence annual mode described below. Use this explicit mode when the user wants deliberate work-receipt accomplishments plus supplemental mined checkin evidence.

If the argument is missing or malformed, print usage and stop; do not guess.

## Input Selection

For `month`, consume the individual `sr-*.md` status reports whose frontmatter `window_end` falls inside the month. Do not feed the monthly output back into its own input selection.

For `year`, the evidence base is the Perforce year dir: consume every `ck-monthly-YYYY-MM.md` rollup present under `<vault>\Checkins\perforce\YYYY\`. Status reports are not consumed for annual runs (they feed the monthly rollups instead).

**Monthly idempotency:** if the monthly output file already exists, print "Rollup for <window> already exists: <path> - skipping." and stop. Do not overwrite.

**Annual updates (living document):** the annual output is a living document, updated in place on re-runs.
- If the output does not exist: generate it from all rollups in the year dir.
- If it exists: read its frontmatter `sources` (the rollups consumed so far). Find rollups in the year dir that are not yet in `sources`. If there are none, print "No new checkin evidence since last summary - skipping." and stop. Otherwise update the document in place: fold the new months into `Year in Review`, `Major Accomplishments`, `Technical Leadership`, `Growth & Scope Changes`, and `Themes for Next Year` (re-frame the narrative to cover the full year so far; do not append a changelog), add the new rollups to `sources`, and bump `generated`. Re-evaluate the draft-flagging callout against the current source set.

If zero sources fall in the window, still write the output: "No status reports in window." for monthly runs, or "No checkin rollups in year." for annual runs, as the body of the first section.

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

**Annual body** (`# Annual Review Material — YYYY`): sections `## Year in Review` (3-5 sentence narrative), `## Major Accomplishments` (each with impact framing: what changed, for whom, at what scope), `## Technical Leadership`, `## Growth & Scope Changes`, `## Themes for Next Year`, `## Source Rollups`. Write for a performance-review reader: impact over activity, outcomes over task lists. Evidence comes from the monthly checkin rollups' `## Summary` and `## By Initiative` sections; group by initiative arc across the year, not by month. `## Source Rollups` lists wikilinks to every consumed `ck-monthly-YYYY-MM` rollup.

## Combined Annual Evidence (Compatibility)

For `year YYYY evidence combined`, use the original destination workflow: select status reports by `window_end` within the year, prefer each month's monthly summary when available, and otherwise consume that month's individual status reports. Also collect checkin rollups in the year's `Checkins/perforce/YYYY/YYYY-MM/rollups/` folders and legacy `Checkins/perforce/rollups/ck-*.md` files whose `window` belongs to the year. Deduplicate the same rollup when both layouts contain it.

Write `<vault>\Reviews\annual-YYYY.md`. If it exists, skip without overwriting, as in the original workflow. Include the normal annual narrative sections, a separately labeled `## Supplemental Checkin Evidence` section only when checkin rollups exist, and `## Source Reports` listing all consumed status reports and a separate sub-list of checkin rollups. Keep mined Perforce evidence distinguishable from deliberate work-receipt accomplishments. Apply the same draft-source warning and cost-ledger rules. The default `year YYYY` Perforce living-review behavior above remains unchanged.

## Cost Ledger

Append one row to `<vault>\Receipts\cost-ledger.csv` (same header as always) with topic_slug `monthly-YYYY-MM` or `annual-YYYY`.

## Output

Print exactly: the output file path on one line, then `sources: N reports (M drafts)`.
