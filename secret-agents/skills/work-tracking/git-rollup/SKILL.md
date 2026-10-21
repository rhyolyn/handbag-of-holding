---
name: git-rollup
description: "Use when the user asks to summarize GitHub source-control receipts by initiative for a reporting window."
---

# Git Rollup

**Category:** Reporting · **Updated:** 2026-10-20

Summarize GitHub receipts by initiative for a reporting window. This is an intermediate view, not the annual evidence base.

## Workspace contract

Validate before reading or writing with `python -m secret_agents_work_tracking workspace check [--config PATH | --vault PATH]`. Follow [Worky data vault paths](../../../runbooks/worky-vault-paths.md). Read and write only through the named `git_checkins` location and its `<host>/<owner>/<repo>/YYYY/YYYY-MM/` partitions.

## Input selection

Select receipts whose evidence dates overlap the requested Pacific window. Deduplicate GitHub evidence before synthesis: retain a merged pull request, exclude only the standalone commits in its `pr_commit_urls`, and retain reviews. A missing or malformed receipt is an explicit incomplete-evidence diagnostic, not a silent omission.

## Output

Write one idempotent rollup with initiative themes, factual completed work, status-bullet candidates, and a `## Source Receipts` section containing every contributing receipt link. If no evidence matches, write an explicit no-evidence rollup. Return the output path and receipt count.
