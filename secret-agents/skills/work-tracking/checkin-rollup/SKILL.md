---
name: checkin-rollup
description: "Use when the user asks to summarize Perforce checkin receipts over a bi-weekly, monthly, or custom window, or explicitly invokes @skill checkin-rollup with a cadence argument. Groups checkin receipts by initiative arc and produces a summary with status-bullet candidates."
---

# Checkin Rollup

**Category:** Reporting · **Updated:** 2026-10-16

Summarize the checkin receipts under `Checkins/perforce/` over a reporting window, grouped by initiative arc. Produces a rollup with themes, per-arc completed work, impact, and ready-to-paste status bullets. Feeds the annual performance review (via `report-rollup`).

## Input

Exactly one window argument, required:

- `biweekly <end-date>` - the 14 days ending at the most recent Tue-or-Thu 06:00 local Pacific boundary at or before `<end-date>` (mirrors `report-status` boundaries).
- `month YYYY-MM` - 1st of that month 00:00 to 1st of the next month 00:00 local Pacific.
- `window <start>..<end>` - verbatim dates (local Pacific).

If the argument is missing or malformed, print usage and stop; do not guess.

## Vault Layout

Resolve `<vault>` using [Worky data vault paths](../../../runbooks/worky-vault-paths.md) before reading inputs or creating outputs.

- Inputs: `<vault>\Checkins\perforce\YYYY\YYYY-MM\CK-*.md` (only files with YAML frontmatter containing `date`).
- Output: `<vault>\Checkins\perforce\YYYY\YYYY-MM\rollups\<label>.md`, where `YYYY\YYYY-MM` is the month folder of the window's end date (create `rollups\` inside it if needed).
- Cost ledger: `<vault>\Receipts\cost-ledger.csv`.

Label by cadence: `ck-biweekly-<end YYYY-MM-DD>`, `ck-monthly-<YYYY-MM>`, or `ck-window-<start>-<end>`.

## Input Selection

A checkin receipt belongs to the window if its frontmatter `date` is `>= window_start` and `< window_end`. Scan only the month folders that overlap the window.

- **Idempotency:** if the output file already exists, print `Rollup for <window> already exists: <path> - skipping.` and stop. Do not overwrite.
- **Noise:** receipts with `noise: true` are excluded from the substantive sections but counted in one line.
- If zero substantive receipts fall in the window, still write the output with "No substantive checkins in window." in the Summary.

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
# Checkin Rollup — <label>

## Summary
- 2-4 bullets of high-level themes across the window's checkins (what the period was about, at the arc level).

## By Initiative
### <arc name>
- Completed bullets (merge the receipts' Summary/Changes into arc-level outcomes).
- **Impact:** one line on what this arc's work changed for the team/product.
(repeat per arc, most-significant first)

## Status Bullet Candidates
- Verbatim Suggested Status Bullets from the receipts, deduplicated.

## Excluded
- N noise CLs (stream/binary) in window.

## Source Checkins
- Wikilink list mirroring `sources`.
```

Keep bullets factual. Do not invent work that is not in a receipt.

## Cost Ledger

Append one row to the cost ledger with `topic_slug` = the rollup label, using this session's model and token usage. Never invent figures.

## Output

Print exactly: the output file path on one line, then `sources: N receipts (M noise excluded)`.
