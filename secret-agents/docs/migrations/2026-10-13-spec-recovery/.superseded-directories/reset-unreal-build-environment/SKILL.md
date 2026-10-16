---
name: reset-unreal-build-environment
description: "Use when the user invokes reset-unreal-build-environment as an alias for unreal-reset-build-env."
metadata:
  category: unreal
  kind: alias
  alias_of: unreal-reset-build-env
---

# reset-unreal-build-environment

This skill is a shorthand alias for `unreal-reset-build-env`.

## Behavior

1. Read [the canonical skill](../unreal-reset-build-env/SKILL.md).
2. Forward every argument unchanged, including any flags, `help`, or `--help`.
3. Follow that skill's workflow and output contract. If the canonical file is missing, report the missing path instead of inventing a replacement workflow.

## Examples

- `@skill reset-unreal-build-environment`
- `/reset-unreal-build-environment` with the same arguments supported by `unreal-reset-build-env`.
