---
name: mucpd
description: Alias for update-claude-pricing-doc. Use when the user asks to refresh or update Claude API pricing, or when claude-pricing.json is stale (>1 week old). WebFetches the official Anthropic pricing docs page, extracts only per-model token rates, and writes them to output/claude-pricing.json. Cheap and context-light; never invokes the claude-api skill.
---

<!-- generated:update-claude-pricing-doc:2026-10-12 -->
# mucpd

Alias for `update-claude-pricing-doc`. Pass all arguments through unchanged.

## Behavior

Follow the `update-claude-pricing-doc` skill exactly. Treat all arguments passed to `/mucpd` as arguments for `/update-claude-pricing-doc`.
