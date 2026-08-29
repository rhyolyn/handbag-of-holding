---
name: report-receipt
description: Use when the user asks to create or update a work receipt, WR, handoff note, status receipt, completion receipt, progress receipt, or explicitly invokes @skill report-receipt; especially when saving analysis, summarizing engineering work, or preserving text verbatim in a receipt.
---

# Work Receipt Skill

Use this skill whenever the user asks for a work summary, handoff note, status receipt, completion receipt, or progress receipt.

## File Output Target

- Write the receipt to the current month's folder of the `worky` checkout this skill lives in: `<skill base dir>\..\..\..\Receipts\YYYY\YYYY-MM\` where `YYYY-MM` is the receipt's end date (the skill sits at `<worky root>\Agent\skills\report-receipt`). Create the month folder if it does not exist.
- Known checkouts: `D:\git\worky` (work machine), `C:\git\worky` (home machine) — but always prefer the resolved relative path over these.

## Filename Convention

Match the existing pattern in the resolved `Receipts` folder:

- Prefix: `WR-`
- Date segment: `YYYY-MM-DD`
- Separator: `_`
- Topic slug: lowercase, words separated by `-`
- Extension: `.md` (single extension only)

Preferred filename format:

- `WR-YYYY-MM-DD_<topic-slug>.md`

Examples:

- `WR-2026-07-03_buildgraph-cli-runbook-fix.md`
- `WR-2026-07-03_uba-dotnet-process-troubleshooting.md`

## Output Rules

- Output only one markdown document.
- Use exactly the sections and heading levels below.
- Keep bullets concise and factual.
- If information is missing, write `- TBD` in that section.
- For `Handoff`, `Actual Prompt`, and `20/20 Hindsight Corrected Prompt`: write `N/A` if there is nothing to add (not `TBD`).
- Do not add extra sections.
- Save the markdown to a file in the resolved `Receipts` folder (see File Output Target) using the filename convention above.
- After saving, return only:
  - the final file path,
  - a one-line summary of the receipt,
  - the full Efficiency Analysis section (echoed verbatim so the coaching lands immediately).
- Do not echo the rest of the receipt body in chat — the file is the deliverable.

## Verbatim Requests

- If the user asks to write analysis or text verbatim, preserve the requested text exactly.
- Put the verbatim text inside one required section, usually `### Coordination`, as a fenced `text` block.
- Do not paraphrase, clean up, or reformat the verbatim block except for enclosing it in the fence.

## Model Recommendations

Receipt writing is summarization of existing session context plus light judgment (cost analysis, improvement plan). A mid-tier model is sufficient; frontier models add cost, not receipt quality.

- **Claude (Claude Code / API):** Sonnet-class (e.g. `claude-sonnet-4-6`) is the sweet spot; Haiku-class is acceptable for short, clean sessions. In Claude Code the receipt runs on whatever model the session is already using — do not switch models just for the receipt (a model switch invalidates the prompt cache and can cost more than staying on the pricier model).
- **Copilot:** Use an included / low-multiplier model (e.g. GPT-5 mini or GPT-4.1). Do not spend a premium request on a receipt.
- **Codex:** Default codex model at low reasoning effort; raise to medium only if the cost analysis or improvement plan comes out shallow.

## Handoff Guidance

- If further work remains for a future session, write a self-contained prompt the next agent can paste directly to resume work: include the goal, current state, relevant file paths, and any constraints or open decisions.
- The handoff prompt must stand alone — assume the next session has no memory of this one.
- If no further work is needed, write `N/A`.

## Efficiency Analysis Guidance

All subsections below belong inside the `### Efficiency Analysis` block. Write them in order: complete `Actual Prompt` and `20/20 Hindsight Corrected Prompt` first, then read the session transcript and write `AI Cost Analysis`, then write `Human Improvement Plan` last. This ensures the transcript read captures as much session work as possible before the cost numbers are locked in.

### Actual Prompt Guidance

- Copy the verbatim opening prompt (or the first substantive message) the human sent to start this session's work.
- If the task came from a handoff prompt, use that. If it came from a chat message, use that message exactly.
- Write `N/A` if the prompt cannot be reconstructed from context.

### 20/20 Hindsight Corrected Prompt Guidance

- Rewrite the Actual Prompt as it should have been written, knowing everything learned during the session.
- A corrected prompt should: state the goal clearly, include relevant file paths, name constraints and the definition of done, and avoid ambiguity that caused rework or clarifying turns.
- Keep the tone neutral — this is a coaching artifact, not a critique. Be specific about what was missing or unclear.
- Write `N/A` if the Actual Prompt was already optimal.

### AI Cost Analysis Guidance — Claude

Apply this subsection only to Claude sessions.

- Read the session transcript NOW (before writing this section) to capture the most complete token count. Find the current session's `.jsonl` (newest by modified time) in `~/.claude/projects/<project-slug>/` (Windows: `%USERPROFILE%\.claude\projects\<project-slug>\`), parse each line as JSON, and total the `message.usage` fields: `input_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, `output_tokens`.
- Read `<skill base dir>\..\update-claude-pricing-doc\output\claude-pricing.json` for model rates (rates in USD per 1M tokens; cache read = 0.1× input, cache write = 1.25× input). Check the `updated` date and print one of:
  - `🤖 Claude pricing data  ✅ <age> old` — if ≤ 7 days old
  - `🤖 Claude pricing data  ⚠️ <age> old — run @skill update-claude-pricing-doc to refresh` — if > 7 days old
  - If the file is missing, fall back to the `claude-api` skill for current rates and warn that the cache is absent.
- Price the totals at the session model's rates from the pricing file: uncached input at base input rate, cache reads at 0.1× base, cache writes at 1.25× base, output at output rate. Report a per-category table (tokens, rate, cost) plus the total. Note that on a subscription plan the marginal dollar cost is $0 and the figure is API-equivalent value.
- If no transcript is available (other tools, or the file cannot be found), fall back to estimation from session evidence (turn count, tool calls, context growth, model in use) and label estimates as estimates — never invent exact figures.
- Bullet the session's top cost drivers: what consumed the most tokens, and why. If cache writes dominate, the usual cause is idle gaps past the 5-minute cache TTL forcing full-context re-writes.
- Call out avoidable spend explicitly: cache re-writes from idle gaps, re-explained context, exploratory searches caused by vague direction, redundant file reads, abandoned work.
- Append one row to `Receipts\cost-ledger.csv` (create with header if missing): `date,topic_slug,model,input_tokens,cache_read_tokens,cache_write_tokens,output_tokens,total_usd`. This builds the cross-session trend the coaching is measured against.

### AI Cost Analysis Guidance — Codex

Apply this subsection only to Codex sessions.

- Read the session rollout NOW (before writing this section) to capture the latest cumulative usage. Locate the current `.jsonl` under `~/.codex/sessions/YYYY/MM/DD/` (Windows: `%USERPROFILE%\.codex\sessions\YYYY\MM\DD\`). Match the current session by `session_meta.payload.cwd`, session ID when available, and modification time; do not assume the newest file belongs to this session when several sessions are active.
- Parse the final `event_msg` whose `payload.type` is `token_count`. Read `payload.info.total_token_usage` once: it is a cumulative snapshot, so never sum multiple `token_count` events. Record `input_tokens`, `cached_input_tokens`, and `output_tokens`. Treat `reasoning_output_tokens` as a diagnostic subset of output, not an additional billable category, unless the provider's authoritative documentation explicitly says otherwise.
- Calculate uncached input as `input_tokens - cached_input_tokens`. Read the model from the applicable `turn_context.payload.model`; if the model changed during the session and the rollout does not expose per-model usage, disclose that exact cost allocation is unavailable rather than assigning every token to the last model.
- Separate three measures clearly: token consumption, subscription/rate-limit consumption, and dollar cost. Codex `rate_limits` percentages are quota-window utilization, not API charges. On an included subscription, report marginal dollar cost as `$0` while still reporting tokens and optimization opportunities.
- Calculate API-equivalent value only when the exact model maps unambiguously to a publicly priced API model. Use the current official OpenAI pricing for uncached input, cached input, and output; cite or name the pricing source and retrieval date. Internal, preview, or Codex-specific model aliases may not have a public API price—report `N/A (no authoritative public rate)` instead of substituting a similarly named model or inventing a figure.
- Report a per-category table with uncached input, cached input, and output tokens; include rates and costs when authoritative rates exist. Label any fallback derived from session evidence as an estimate and show the assumptions.
- Identify top cost drivers from transcript evidence: large instructions or file reads repeatedly carried in context, high tool-output volume, repeated searches, re-explained context, abandoned work, excessive reasoning effort, and extra turns caused by ambiguous direction. Use deltas between cumulative `token_count` snapshots to attribute expensive turns when useful.
- Recommend concrete improvements tied to observed events and quantify them in turns, tool calls, tokens, or an explicitly estimated share. Do not claim that idle time causes Anthropic-style cache writes in Codex unless the rollout or current OpenAI documentation proves it for this session.
- Append one row to `Receipts\cost-ledger.csv` using the existing header: `date,topic_slug,model,input_tokens,cache_read_tokens,cache_write_tokens,output_tokens,total_usd`. For Codex, store `cached_input_tokens` in `cache_read_tokens`, store `0` in `cache_write_tokens`, and store a blank `total_usd` when no authoritative API-equivalent rate exists. Explain this compatibility mapping in the receipt if it could be mistaken for native Codex field names.

### Human Improvement Plan Guidance

- Purpose: coach the human toward maximum token efficiency in future sessions.
- Close the loop first: read the previous receipt's Human Improvement Plan (next-newest `WR-*.md` in the Receipts folder) and open with a one-bullet delta — which prior advice was followed this session, which was not. Skip if no prior receipt exists.
- Then session-specific bullets. Each must trace to a concrete event in this session, name the costly behavior, quantify the waste (turns, tool calls, or estimated share of session cost), and state the fix. Example: `- Three follow-ups re-explained the same context; one upfront message with file paths would have cut ~40% of turns.`
- Be direct and specific. Name the behavior and the fix plainly; no softening, no praise padding.
- Follow with up to 3 standing habits (general best practices) relevant to this user's recurring patterns — e.g. batch related asks into one message, give file paths instead of descriptions, and state constraints and the definition of done before work starts. Include the 5-minute prompt-cache advice only for Claude sessions where the transcript supports that diagnosis; do not generalize it to Codex.
- If the session was already efficient, say so in one bullet and list what to keep doing.

## Required Output Format

```markdown
## Work Receipt

### Goal
-

### Changes
-

### Files / Systems
-

### Technical Decisions
-

### Coordination
-

### Risks / Unknowns
-

### Handoff
-

### Suggested Status Bullet
-

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
