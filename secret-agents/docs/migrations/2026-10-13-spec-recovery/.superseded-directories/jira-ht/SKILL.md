---
name: jira-ht
description: "Use when the user invokes jira-ht as an alias for jira-human-ticket-create."
metadata:
  category: jira
  kind: alias
  alias_of: jira-human-ticket-create
---

# jira-ht

This skill is a shorthand alias for `jira-human-ticket-create`.

## Behavior

1. Read [the canonical skill](../jira-human-ticket-create/SKILL.md).
2. Forward every argument unchanged, including any flags, `help`, or `--help`.
3. Follow that skill's workflow and output contract. If the canonical file is missing, report the missing path instead of inventing a replacement workflow.

## Examples

- `@skill jira-ht`
- `/jira-ht` with the same arguments supported by `jira-human-ticket-create`.
