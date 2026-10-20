---
name: perforce-rollup
description: "Use when the user asks to summarize Perforce source-control receipts over a bi-weekly, monthly, or custom window, or explicitly invokes @skill perforce-rollup with a cadence argument."
---

# Perforce Rollup

**Category:** Reporting · **Updated:** 2026-10-16

Summarize Perforce receipts over a reporting window, grouped by initiative. Produce themes, completed work, impact, and status-bullet candidates. This is an intermediate source-specific view, not the annual evidence base.

## Input

Exactly one window argument, required:

- `biweekly <end-date>` - the 14 days ending at the most recent Tue-or-Thu 06:00 local Pacific boundary at or before `<end-date>` (mirrors `report-status` boundaries).
- `month YYYY-MM` - 1st of that month 00:00 to 1st of the next month 00:00 local Pacific.
- `window <start>..<end>` - verbatim dates (local Pacific).

If the argument is missing or malformed, print usage and stop; do not guess.

## Workspace contract

Before accessing data, validate the selected vault with `python -m secret_agents_work_tracking workspace check --vault <path>` (or `--config <path>`). Follow [Worky data vault paths](../../../runbooks/worky-vault-paths.md).

- Read and write only through the named `perforce_checkins` location; use its `YYYY/YYYY-MM` partition and a `rollups/` child for the output.
- Operational usage, if requested, belongs in the named `ledgers` location and never becomes evidence.

Label by cadence: `ck-biweekly-<end YYYY-MM-DD>`, `ck-monthly-<YYYY-MM>`, or `ck-window-<start>-<end>`.

## Input Selection

A Perforce receipt belongs to the window if its `occurred_start` is `>= window_start` and `< window_end`. Scan only the month folders that overlap the window.

- **Idempotency:** if the output file already exists, print `Rollup for <window> already exists: <path> - skipping.` and stop. Do not overwrite.
- **Noise:** receipts with `noise: true` are excluded from the substantive sections but counted in one line.
- If zero substantive receipts fall in the window, still write the output with "No substantive Perforce receipts in window." in the Summary.

## Output Format

Frontmatter:

```yaml
---
status: draft
window: 2026-10            # or the biweekly/window label
sources:
  - "[[CK-7399-unity-build-fix]]"
generated: 2026-10-12T11:55-07:00
---
```

- `sources`: one wikilink per substantive receipt (filename without extension).
- `generated`: current local timestamp with the correct Pacific offset (-07:00 PDT / -08:00 PST).

Body:

```markdown
# Perforce Rollup — <label>

## Summary
- 2-4 bullets of high-level themes across the window's Perforce work.

## By Initiative
### <arc name>
- Completed bullets (merge the receipts' Summary/Changes into arc-level outcomes).
- **Impact:** one line on what this arc's work changed for the team/product.
(repeat per arc, most-significant first)

## Status Bullet Candidates
- Verbatim Suggested Status Bullets from the receipts, deduplicated.

## Excluded
- N noise CLs (stream/binary) in window.

## Source Receipts
- Wikilink list mirroring `sources`.
```

Keep bullets factual. Do not invent work that is not in a receipt.

## Output

Print exactly: the output file path on one line, then `sources: N receipts (M noise excluded)`.
