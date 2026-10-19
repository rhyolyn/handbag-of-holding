---
name: status-report-create
description: "Use when the user invokes status-report-create as an alias for report-status."
metadata:
  category: report
  kind: alias
  alias_of: report-status
---

# status-report-create

This skill is a shorthand alias for `report-status`.

## Behavior

1. Read [the canonical skill](../report-status/SKILL.md).
2. Forward every argument unchanged, including any flags, `help`, or `--help`.
3. Follow that skill's workflow and output contract. If the canonical file is missing, report the missing path instead of inventing a replacement workflow.

## Examples

- `@skill status-report-create`
- `/status-report-create` with the same arguments supported by `report-status`.
