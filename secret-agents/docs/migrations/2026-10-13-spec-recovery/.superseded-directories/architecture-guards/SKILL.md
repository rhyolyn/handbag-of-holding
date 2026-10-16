---
name: architecture-guards
description: "Use when the user invokes architecture-guards as an alias for clean-code-architecture-guards."
metadata:
  category: clean-code
  kind: alias
  alias_of: clean-code-architecture-guards
---

# architecture-guards

This skill is a shorthand alias for `clean-code-architecture-guards`.

## Behavior

1. Read [the canonical skill](../clean-code-architecture-guards/SKILL.md).
2. Forward every argument unchanged, including any flags, `help`, or `--help`.
3. Follow that skill's workflow and output contract. If the canonical file is missing, report the missing path instead of inventing a replacement workflow.

## Examples

- `@skill architecture-guards`
- `/architecture-guards` with the same arguments supported by `clean-code-architecture-guards`.
