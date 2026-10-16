---
name: qas
description: "Use when the user invokes qas as an alias for query-all-skills."
argument-hint: "[--target <dir>] [--help]"
user-invocable: true
metadata:
  category: agent
  kind: alias
  alias_of: query-all-skills
---

# qas

This skill is a shorthand alias for `query-all-skills`.

## Behavior

1. Read [the canonical skill](../query-all-skills/SKILL.md).
2. Forward every argument unchanged, including any flags, `help`, or `--help`.
3. Follow that skill's workflow and output contract. If the canonical file is missing, report the missing path instead of inventing a replacement workflow.

## Examples

- `@skill qas`
- `/qas` with the same arguments supported by `query-all-skills`.

When `--help` is supplied, present the canonical usage with `/qas` as the invocation and identify `/query-all-skills` as its equivalent. Help performs no scan.
