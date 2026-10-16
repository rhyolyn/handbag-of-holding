---
name: ugs-pcb-release
description: "Use when the user invokes ugs-pcb-release as an alias for unreal-ugs-release."
metadata:
  category: unreal
  kind: alias
  alias_of: unreal-ugs-release
---

# ugs-pcb-release

This skill is a shorthand alias for `unreal-ugs-release`.

## Behavior

1. Read [the canonical skill](../unreal-ugs-release/SKILL.md).
2. Forward every argument unchanged, including any flags, `help`, or `--help`.
3. Follow that skill's workflow and output contract. If the canonical file is missing, report the missing path instead of inventing a replacement workflow.

## Examples

- `@skill ugs-pcb-release`
- `/ugs-pcb-release` with the same arguments supported by `unreal-ugs-release`.
