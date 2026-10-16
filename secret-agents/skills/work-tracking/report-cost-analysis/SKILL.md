---
name: report-cost-analysis
description: Use when a work receipt needs optional AI token and cost analysis or an efficiency improvement plan, including after report-receipt --show-cost.
---

# Report Cost Analysis

**Category:** Reporting · **Updated:** 2026-10-16

Add the optional `### Efficiency Analysis` block to a work receipt. `report-receipt --show-cost` invokes this workflow after its standard receipt is drafted; it is the only path that includes cost analysis in a new receipt.

## Inputs and Output

- From `report-receipt --show-cost`, use the drafted receipt, its resolved output path, and its topic slug.
- When invoked directly, resolve `<vault>` with [Worky data vault paths](../../../runbooks/worky-vault-paths.md), then require the target receipt path and enough current-session context to identify the transcript. If either is unavailable, refuse clearly rather than guessing.
- Add one `### Efficiency Analysis` section after `### Suggested Status Bullet`. If the target already has that section, replace that section rather than duplicating it.
- Do not modify any other receipt section. Return the completed section to `report-receipt`; direct invocation returns the receipt path and the completed section.

## Sequence

Write the subsections in this order: `Actual Prompt`, `20/20 Hindsight Corrected Prompt`, `AI Cost Analysis`, then `Human Improvement Plan`. Read the transcript immediately before the cost analysis so it captures the most complete usage snapshot.

### Actual Prompt

- Copy the verbatim opening human prompt or first substantive message. For a handoff, use the handoff prompt.
- Write `N/A` when it cannot be reconstructed.

### 20/20 Hindsight Corrected Prompt

- Rewrite the opening prompt with the known goal, relevant paths, constraints, and definition of done.
- Keep it neutral and concrete; it is coaching, not a critique.
- Write `N/A` when the actual prompt was already optimal.

## AI Cost Analysis — Claude

Apply this only to Claude sessions.

- Read the current session transcript from `~/.claude/projects/<project-slug>/` and total `message.usage.input_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, and `output_tokens`.
- Read `<agent-root>/skills/maintenance/update-claude-pricing-doc/output/claude-pricing.json`. Report its age: `✅` when no older than 7 days; otherwise warn to run `@skill update-claude-pricing-doc`. If missing, use `claude-api` for current rates and disclose the missing cache.
- Price uncached input at the base rate, reads at 0.1×, writes at 1.25×, and output at the output rate. Report tokens, rates, costs, total API-equivalent value, and `$0` marginal subscription cost when applicable.
- If the transcript is unavailable, label a session-evidence estimate as an estimate. Never invent exact figures.
- Name top cost drivers and avoidable spend. If cache writes dominate, identify idle gaps past the five-minute cache TTL as the usual cause; otherwise do not speculate about cache rewrites.
- Append exactly one row for this receipt to `Receipts/cost-ledger.csv`, creating the header when absent: `date,topic_slug,model,input_tokens,cache_read_tokens,cache_write_tokens,output_tokens,total_usd`.

## AI Cost Analysis — Codex

Apply this only to Codex sessions.

- Locate the current rollout in `~/.codex/sessions/YYYY/MM/DD/` by cwd, session ID when available, and modification time. Do not assume the newest file belongs to this session.
- From the final `event_msg` with `payload.type` `token_count`, read one cumulative `payload.info.total_token_usage` snapshot: `input_tokens`, `cached_input_tokens`, and `output_tokens`. Treat reasoning output as a subset of output unless authoritative documentation says otherwise.
- Calculate uncached input as `input_tokens - cached_input_tokens`. Read the model from `turn_context.payload.model`; if model-specific usage is unavailable after a model change, disclose that exact allocation is unavailable.
- Separate tokens, rate-limit consumption, and dollar cost. Rate-limit percentages are not API charges. Report `$0` marginal subscription cost. Calculate API-equivalent value only when the exact model maps unambiguously to a publicly priced API model: use current official OpenAI prices for uncached input, cached input, and output, and name the source and retrieval date. Otherwise use `N/A (no authoritative public rate)`.
- Report a category table for uncached input, cached input, and output; include rates and costs when authoritative rates exist. Label estimates and their assumptions. Identify evidence-based cost drivers and concrete improvements tied to observed events, quantified in turns, tool calls, tokens, or an explicit estimated share. Do not apply Claude cache-TTL claims to Codex without evidence.
- Append exactly one row for this receipt to `Receipts/cost-ledger.csv` using the Claude-compatible header. Store `cached_input_tokens` in `cache_read_tokens`, `0` in `cache_write_tokens`, and blank `total_usd` when no authoritative API-equivalent rate exists; explain this mapping in the receipt when needed.

## Human Improvement Plan

- Read the next-newest `WR-*.md` first. Open with one bullet stating whether its prior advice was followed; skip this when no earlier receipt exists.
- Then write session-specific, direct recommendations. Each names the costly behavior, quantifies the waste in turns, tool calls, tokens, or an explicit estimate, and states the fix. Do not soften the advice with praise padding.
- Add at most three relevant standing habits. Include five-minute prompt-cache advice only for Claude sessions where transcript evidence supports it.
- When the session was already efficient, say what to keep doing in one bullet.

## Required Output Format

```markdown
### Efficiency Analysis

##### Actual Prompt
-

##### 20/20 Hindsight Corrected Prompt
-

#### AI Cost Analysis
-

#### Human Improvement Plan
-
```
