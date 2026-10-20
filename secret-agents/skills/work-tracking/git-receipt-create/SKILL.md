---
name: git-receipt-create
description: "Use when the user asks to record one merged GitHub pull request, standalone commit, or submitted review as work evidence."
---

# Git Receipt Create

**Category:** Reporting · **Updated:** 2026-10-20

Record one GitHub work item from saved `gh` JSON. A merged pull request is the primary work item; a commit included in it is not separate evidence. Reviews remain distinct evidence. Never query issues.

## Workspace contract

Validate the selected vault before accessing source data:

```text
python -m secret_agents_work_tracking workspace check [--config PATH | --vault PATH]
```

Follow [Worky data vault paths](../../../runbooks/worky-vault-paths.md). Write only through the named `git_checkins` location, under `<host>/<owner>/<repo>/YYYY/YYYY-MM/`.

## Procedure

1. Confirm `gh auth status` succeeds. If it does not, stop and tell the user to authenticate with `gh auth login`.
2. Save the relevant `gh` JSON result: an authored merged pull request including commit URLs, an authored standalone commit, or a submitted review. Do not substitute an empty result after a query error.
3. Normalize it with `GitHubReceiptParser`. Its stable `source_id` is the canonical GitHub URL; `github_activity` is `merged_pull_request`, `commit`, or `review`.
4. For a merged pull request, retain every contained canonical commit URL in `pr_commit_urls`. Before writing, parse existing evidence in that repository-month: equal identity plus normalized content skips; different material is a conflict; never overwrite.
5. Write a factual receipt with all common evidence fields and a source link. A merged PR receipt absorbs its included commit receipts; a standalone commit is written only when no merged PR receipt contains its URL.

## Output

Return the saved receipt path, canonical source URL, activity type, and whether it was written, skipped, or refused as a conflict.
