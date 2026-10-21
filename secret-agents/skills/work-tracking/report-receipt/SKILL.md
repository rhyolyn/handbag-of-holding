---
name: report-receipt
description: Use when the user asks to create or update a work receipt, WR, handoff note, status receipt, completion receipt, progress receipt, or explicitly invokes @skill report-receipt; especially when saving analysis, summarizing engineering work, or preserving text verbatim in a receipt.
---

# Work Receipt Skill

**Category:** Reporting · **Updated:** 2026-10-20

Use this skill whenever the user asks for a work summary, handoff note, status receipt, completion receipt, or progress receipt.

## Arguments

- *(none)* — create the standard receipt only.
- `--show-cost` — after drafting the standard receipt, apply `report-cost-analysis` to append the optional `### Efficiency Analysis` section. Use this only when the user asks for cost, token, or efficiency coaching.

`--show-cost` is opt-in. A standard receipt must not read a session transcript, inspect pricing, or append a cost-ledger row.

## Workspace contract

Before accessing data, validate the selected vault with `python -m secret_agents_work_tracking workspace check --vault <path>` (or `--config <path>`). Follow [Worky data vault paths](../../../runbooks/worky-vault-paths.md).

Write only through the resolver-owned `receipts` location, partitioned as `YYYY/YYYY-MM` by the receipt end date. Create the month folder only after validation.

## Filename Convention

Use this filename pattern in the resolved `receipts` location:

- Prefix: `WR-`
- Date segment: `YYYY-MM-DD`
- Separator: `_`
- Topic slug: lowercase, words separated by `-`
- Extension: `.md` (single extension only)

Preferred filename format:

- `WR-YYYY-MM-DD_<topic-slug>.md`

Examples:

- `WR-2026-07-03_buildgraph-cli-runbook-fix.md`
- `WR-2026-07-03_uba-dotnet-process-troubleshooting.md`

## Output Rules

- Output only one markdown document.
- Use exactly the sections and heading levels below.
- Keep bullets concise and factual.
- If information is missing, write `- TBD` in that section.
- For `Handoff`, write `N/A` if there is nothing to add (not `TBD`).
- Do not add extra sections unless `--show-cost` is supplied.
- Save the markdown to a file in the resolved `receipts` location using the filename convention above.
- After saving, return only:
  - the final file path,
  - a one-line summary of the receipt,
  - the full Efficiency Analysis section only when `--show-cost` was supplied.
- Do not echo the rest of the receipt body in chat — the file is the deliverable.

## Verbatim Requests

- If the user asks to write analysis or text verbatim, preserve the requested text exactly.
- Put the verbatim text inside one required section, usually `### Coordination`, as a fenced `text` block.
- Do not paraphrase, clean up, or reformat the verbatim block except for enclosing it in the fence.

## Model Recommendations

Receipt writing is summarization of existing session context plus light judgment. A mid-tier model is sufficient; frontier models add cost, not receipt quality.

- **Claude (Claude Code / API):** Sonnet-class is the sweet spot; Haiku-class is acceptable for short, clean sessions. In Claude Code, use the session model rather than switching just for a receipt.
- **Copilot:** Use an included or low-multiplier model. Do not spend a premium request on a receipt.
- **Codex:** Default Codex model at low reasoning effort is sufficient.

## Handoff Guidance

- If further work remains for a future session, write a self-contained prompt the next agent can paste directly to resume work: include the goal, current state, relevant file paths, and any constraints or open decisions.
- The handoff prompt must stand alone — assume the next session has no memory of this one.
- If no further work is needed, write `N/A`.

## Required Output Format

```markdown
---
kind: work-receipt
occurred_start: YYYY-MM-DD
occurred_end: YYYY-MM-DD
source_system: manual
source_id: manual:<UUID>
initiatives: [Area/Initiative]
tags: [A]
status: draft
sources: []
---

## Work Receipt

### Goal
-

### Changes
-

### Files / Systems
-

### Technical Decisions
-

### Coordination
-

### Risks / Unknowns
-

### Handoff
-

### Suggested Status Bullet
-
```
