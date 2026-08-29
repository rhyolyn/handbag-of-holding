---
name: ready-player-one
description: Use when the user invokes @skill ready-player-one (or /ready-player-one) as a shorthand alias for the agent-preflight environment check before a batched prompt or complex task.
---

# ready-player-one

This skill is a shorthand alias for agent-preflight. (Ready Player One: are we ready to start? Run the preflight.)

## Behavior

1. Read `<skill base dir>\..\agent-preflight\SKILL.md`.
2. Follow that skill exactly.
3. Treat all user arguments passed to `@skill ready-player-one` (or `/ready-player-one`) as arguments for `agent-preflight`.

## Examples

- `/ready-player-one`
- `@skill ready-player-one — preflight before this batch.`
