---
name: work-receipt-create
description: "Use when the user invokes work-receipt-create as an alias for report-receipt."
metadata:
  category: report
  kind: alias
  alias_of: report-receipt
---

# work-receipt-create

This skill is a shorthand alias for `report-receipt`.

## Behavior

1. Read [the canonical skill](../report-receipt/SKILL.md).
2. Forward every argument unchanged, including any flags, `help`, or `--help`.
3. Follow that skill's workflow and output contract. If the canonical file is missing, report the missing path instead of inventing a replacement workflow.

## Examples

- `@skill work-receipt-create`
- `/work-receipt-create` with the same arguments supported by `report-receipt`.
