---
name: git-receipt-range
description: "Use when the user asks to backfill GitHub work evidence for a date range."
---

# Git Receipt Range

**Category:** Reporting · **Updated:** 2026-10-20

Backfill GitHub work evidence for a date range through `git-receipt-create`. Never query issues.

## Workspace contract

Validate before accessing data with `python -m secret_agents_work_tracking workspace check [--config PATH | --vault PATH]`. Follow [Worky data vault paths](../../../runbooks/worky-vault-paths.md), and pass the same named `git_checkins` location to each item workflow.

## Procedure

1. Confirm `gh auth status` succeeds; otherwise stop with the `gh auth login` recovery action.
2. Query saved JSON only for authored merged pull requests (including commits), authored standalone commits, and submitted reviews within the requested Pacific date range. Exclude issues.
3. Send each result to `git-receipt-create`. Process merged pull requests before commits so the shared deduplication contract retains the PR and removes included commits.
4. Continue independent items after a material conflict or failed source query, recording each explicit failure. Do not manufacture an empty receipt.

## Output

Print the range, counts for merged PRs, standalone commits, reviews, written receipts, skipped identical receipts, conflicts, and failed source queries; include the named `git_checkins` folders.
