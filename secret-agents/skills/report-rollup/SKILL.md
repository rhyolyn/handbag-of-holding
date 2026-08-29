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
