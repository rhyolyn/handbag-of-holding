---
name: rut
description: "Use when the user invokes rut as an alias for run-unit-tests."
argument-hint: "[--target <dir>] [--fix] [--help]"
user-invocable: true
metadata:
  category: python
  kind: alias
  alias_of: run-unit-tests
---

# rut

This skill is a shorthand alias for `run-unit-tests`.

## Behavior

1. Read [the canonical skill](../run-unit-tests/SKILL.md).
2. Forward every argument unchanged, including any flags, `help`, or `--help`.
3. Follow that skill's workflow and output contract. If the canonical file is missing, report the missing path instead of inventing a replacement workflow.

## Examples

- `@skill rut`
- `/rut` with the same arguments supported by `run-unit-tests`.

When `--help` is supplied, present the canonical usage with `/rut` as the invocation and identify `/run-unit-tests` as its equivalent. Help performs no setup or execution.
