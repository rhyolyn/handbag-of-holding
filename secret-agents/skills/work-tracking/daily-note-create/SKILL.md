---
name: daily-note-create
description: Use when the user asks to create or normalize a daily work-context note for a local Pacific date.
---

# Daily Note Create

**Category:** Reporting · **Updated:** 2026-10-20

Create one daily context artifact. It records chronology and links to related evidence; it does not silently become source-control evidence.

## Input

Accept `date YYYY-MM-DD`; default to the current date in the configured Pacific timezone. Refuse malformed dates rather than guessing.

## Workspace contract

Before accessing data, validate the selected vault with `python -m secret_agents_work_tracking workspace check --vault <path>` (or `--config <path>`). Follow [Worky data vault paths](../../../runbooks/worky-vault-paths.md).

Write only through the resolver-owned `daily_notes` location, partitioned as `YYYY/YYYY-MM/daily-YYYY-MM-DD.md`. Resolve related evidence through its named location; do not construct legacy vault paths.

## Idempotence

The stable identity is `daily:<YYYY-MM-DD>`. Parse any existing output before writing: identical normalized content is a skip; the same ID with different material is a conflict that requires the user's resolution. Never overwrite the conflicting note.

## Output format

```markdown
---
kind: daily-note
occurred_start: YYYY-MM-DD
occurred_end: YYYY-MM-DD
source_system: manual
source_id: daily:YYYY-MM-DD
initiatives: [Area/Initiative]
tags: [A]
status: draft
sources:
  - "[[related-evidence]]"
---

# Daily Note — YYYY-MM-DD

## Context
-

## Work Log
-

## Related Evidence
- [[related-evidence]]

## Risks / Follow-up
-
```

Use `sources: []` and `- None` when no evidence link exists. Keep factual chronology separate from conclusions that belong in a work receipt or report.
