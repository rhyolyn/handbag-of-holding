---
name: agent-preflight
description: Alias for ready-player-one. Run before executing a batched prompt or complex task. Verifies skill visibility, harness permissions, uv health, and no locked build artifacts. Autofixes safe issues; outputs 'ready' or a NOT READY list with exact remediation steps. Use when the user invokes /ready-player-one or @skill ready-player-one.
---

<!-- generated:ready-player-one:2026-10-12 -->
# agent-preflight

Alias for `ready-player-one`. Pass all arguments through unchanged.

## Behavior

Follow the `ready-player-one` skill exactly. Treat all arguments passed to `/agent-preflight` as arguments for `/ready-player-one`.
