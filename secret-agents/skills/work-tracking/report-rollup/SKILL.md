---
name: report-rollup
description: "Use when the user asks to create a monthly or living annual report from combined work evidence."
---

# Report Rollup

**Category:** Reporting · **Updated:** 2026-10-20

Create monthly reports from status reports, then create a living annual review from monthly reports. Perforce and GitHub rollups remain optional source-specific views; neither replaces combined evidence.

## Workspace contract

Validate the selected vault before reading or writing:

```text
python -m secret_agents_work_tracking workspace check [--config PATH | --vault PATH]
```

Follow [Worky data vault paths](../../../runbooks/worky-vault-paths.md). Read status reports through the named `status_reports` location, write monthly reports through `monthly_reports`, and write annual reviews through `annual_reviews`.

## Month

For `month YYYY-MM`, consume only status reports whose Pacific reporting window ends in that calendar month. Do not feed a monthly report into its own input set. Preserve every status-report link in `## Source Reports`; an empty month remains an explicit no-evidence report.

## Year

For `year YYYY`, consume the year's monthly reports only. The annual review is living: preserve its existing source links, add only newly available months, and skip when the source set is unchanged. Refuse a material conflict before any overwrite.

Frame annual synthesis around impact, scope, technical leadership, growth, and next-year themes—not a chronology. Include `## Source Monthly Reports` with every monthly link. Name incomplete-evidence diagnostics prominently instead of treating missing/malformed sources as no work.

## Output

Return the output path and `sources: N reports`; report whether it was created, updated, skipped identical, or refused as a conflict.
