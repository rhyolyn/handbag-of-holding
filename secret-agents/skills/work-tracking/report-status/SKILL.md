---
name: report-status
description: "Use when the user asks for a biweekly or custom status report synthesized from configured work evidence."
---

# Status Report Create

**Category:** Reporting · **Updated:** 2026-10-20

Create one status report from all configured evidence: manual receipts, daily notes, Perforce receipts, and GitHub receipts. This report is a derived artifact; it must link every source it uses.

## Workspace contract

Validate before reading or writing:

```text
python -m secret_agents_work_tracking workspace check [--config PATH | --vault PATH]
```

Follow [Worky data vault paths](../../../runbooks/worky-vault-paths.md). Read the named `receipts`, `daily_notes`, `perforce_checkins`, and `git_checkins` locations. Write only through the named `status_reports` location.

## Selection and idempotence

Use the reporting contract to select Pacific-window evidence, retain source paths and Obsidian links, deduplicate stable identities, and apply GitHub PR-over-commit deduplication. A malformed source makes the evidence set incomplete and must be named in the report; never silently omit it.

An empty valid window still writes a report with `sources: []` and an explicit no-evidence statement. Before writing, compare the candidate with an existing report: equal inputs skip, while materially conflicting output requires user resolution; never overwrite it.

## Report body

Use factual sections for Summary, Completed, In Progress, Leadership / Coordination, Next Steps / Upcoming, and Risks / Blockers. Finish with `## Source Material` containing every consumed source link. Do not invent accomplishments from absent evidence.

## Output

Return the status-report path, `sources: N`, and an incomplete-evidence warning when diagnostics exist.
