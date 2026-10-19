---
name: update-claude-pricing-doc
description: Use when the user asks to refresh or update Claude API pricing, or when claude-pricing.json is stale (>1 week old). WebFetches the official Anthropic pricing docs page, extracts only per-model token rates, and writes them to output/claude-pricing.json. Cheap and context-light; never invokes the claude-api skill.
---

# Update Claude Pricing Doc Skill

Refreshes the cached pricing file used by `work-receipt-create` so it can price sessions without loading the full claude-api skill bundle.

**Do NOT invoke the `claude-api` skill for this — it loads a large reference bundle and floods context. Use WebFetch only.**

## Steps

1. Spawn a subagent with this task: "WebFetch `https://platform.claude.com/docs/en/about-claude/pricing` (fallback: `https://docs.anthropic.com/en/docs/about-claude/pricing`). From the Model pricing table, extract ONLY current (non-retired) models: the model ID and its Base Input Tokens and Output Tokens rates in USD per 1M tokens. If a model has date-dependent pricing (e.g. introductory pricing), use the rate in effect today. Do NOT read any files, invoke any skills, or fetch any other pages. Return ONLY a JSON object with shape: {\"<model-id>\": {\"input\": <rate>, \"output\": <rate>}, ...} — no explanation or other text."

   (The subagent exists because WebFetch may return the full page rather than just the extraction; the subagent absorbs that and returns only the small JSON.)

2. Parse the subagent's returned JSON.

3. Write (overwrite) `<skill base dir>\output\claude-pricing.json` with exactly this shape:

```json
{
  "updated": "YYYY-MM-DD",
  "note": "Rates in USD per 1M tokens. cache_read = 0.1x input, cache_write = 1.25x input.",
  "models": {<subagent_returned_json>}
}
```

- `updated` = today's date in `YYYY-MM-DD` format.
- Merge the subagent's JSON directly into the `models` field.

4. Create `<skill base dir>\output\` if it does not exist.

## Output

Print only:
```
✅ claude-pricing.json updated (YYYY-MM-DD)
```

## When to Run

Run this skill when:
- `work-receipt-create` prints a ⚠️ staleness warning (pricing older than 7 days).
- You know Anthropic has changed model pricing.
- The file `output/claude-pricing.json` does not exist.
