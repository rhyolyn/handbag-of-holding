---
name: status-report-create
description: Use when generating a Tue/Thu status report from work receipts, when a scheduled status-report run fires, or when the user invokes /status-report-create (optionally with an explicit window override like "window 2026-07-07..2026-07-09").
---

# Status Report Create

Generate one status report covering a Tue/Thu reporting window from work receipts. Runs headless on a schedule or on demand.

## Vault Layout

Resolve the vault root from this skill's base directory: `<skill base dir>\..\..\..` (the skill sits at `<worky root>\Agent\skills\status-report-create`).

- Receipts: `<vault>\Receipts\YYYY\YYYY-MM\WR-*.md`
- Reports out: `<vault>\Status Reports\YYYY\YYYY-MM\sr-YYYY-MM-DD.md`
- Template: `<vault>\Templates\Status Report Template.md`
- Cost ledger: `<vault>\Receipts\cost-ledger.csv`

## Window Computation

Report boundaries are Tuesdays and Thursdays at 06:00 local Pacific time.

1. **window_end** = the most recent Tue-or-Thu 06:00 boundary that is in the past (relative to now). Example: run on Thu 2026-07-16 at 06:05 → window_end is Thu 2026-07-16 06:00. Run on Wed → window_end is Tue 06:00.
2. **window_start** = the `window_end` frontmatter value of the most recent existing status report (newest `sr-*.md` by filename date under `Status Reports/`, reading its YAML frontmatter). Fallback if none exists or none has the frontmatter: the Tue-or-Thu 06:00 boundary immediately before window_end.
3. **Window override:** if invoked with `window <start>..<end>` (dates, e.g. `window 2026-07-07..2026-07-09`), use `<start>T06:00` and `<end>T06:00` local time verbatim and skip steps 1-2.
4. **Idempotency check:** the output filename is `sr-<window_end date as YYYY-MM-DD>.md`. If that file already exists in the target month folder, print "Report for window ending <date> already exists: <path> - skipping." and stop. Do not overwrite.

Deriving window_start from the last report (not from "today") makes catch-up runs correct after missed schedules and makes re-runs idempotent.

## Receipt Collection

A receipt belongs to the window if its **end date** is `>= window_start` and `< window_end`.

- End date = the **last** `YYYY-MM-DD` occurring in the filename. `WR-2026-04-17_to_2026-05-22-nfs_copy.md` ends 2026-05-22; `WR-2026-07-10_optitrack-p4-staging.md` ends 2026-07-10. Multi-day receipts belong to the window in which the work concluded.
- Receipt dates carry no time component; treat a receipt's end date as that day at 06:00 local for the boundary comparison (a receipt dated the same day as window_end is **inside** the window only if window_end's boundary comparison places 06:00 < 06:00 = false — i.e., it lands in the next window; a receipt dated the day of window_start at 06:00 is inside this window).
- Only scan the month folders that overlap the window (`Receipts/YYYY/YYYY-MM/` for each month touched by the window).

If no receipts fall in the window, still write the report: put "No receipts in window." as the sole Summary bullet and leave other sections as single `- None this period.` bullets. An empty period is information, not an error.

## Report Format

Write `Status Reports/YYYY/YYYY-MM/sr-YYYY-MM-DD.md` (create the month folder if needed) where the date is window_end's date, `YYYY`/`YYYY-MM` from window_end. Frontmatter first:

```yaml
---
status: draft
window_start: 2026-07-09T06:00-07:00
window_end: 2026-07-14T06:00-07:00
sources:
  - "[[WR-2026-07-10_optitrack-p4-staging]]"
generated: 2026-07-14T06:02-07:00
---
```

- `sources`: one wikilink per receipt in the window (filename without extension). Empty list if none.
- `generated`: current local timestamp with UTC offset. Use the correct Pacific offset for the date (-07:00 PDT, -08:00 PST).

Body uses exactly the template's sections and heading levels:

```markdown
# Status Report — YYYY-MM-DD

## Summary
## Completed
## In Progress
## Leadership / Coordination
## Next Steps / Upcoming
## Risks / Blockers
## Source Material
### Status Report Candidates
### Related Work Receipts
```

Fill sections from the receipts' content:

- **Summary**: 2-4 bullets of high-level impact and themes across the window's receipts.
- **Completed / In Progress**: derive from each receipt's Goal, Changes, and Handoff sections (a receipt with a non-N/A Handoff usually indicates in-progress work).
- **Leadership / Coordination**: from receipts' Coordination sections; `- None this period.` if all TBD.
- **Next Steps / Upcoming**: from Handoff sections.
- **Risks / Blockers**: from Risks / Unknowns sections; `- None this period.` if none.
- **Status Report Candidates**: each receipt's Suggested Status Bullet, verbatim.
- **Related Work Receipts**: wikilink list mirroring `sources`.

Keep bullets factual and concise. Do not invent work that is not in a receipt.

## Cost Ledger

After writing the report, append one row to `<vault>\Receipts\cost-ledger.csv`:
`date,topic_slug,model,input_tokens,cache_read_tokens,cache_write_tokens,output_tokens,total_usd` — use `sr-YYYY-MM-DD` as topic_slug and this session's model and token usage. Never invent exact figures; label anything derived indirectly as an estimate.

Read usage from the current runtime's own records (below) before writing the row.

### Claude

Total the `message.usage` fields (`input_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, `output_tokens`) across the session's `.jsonl` in `%USERPROFILE%\.claude\projects\<project-slug>\`. Price from `<skill base dir>\..\update-claude-pricing-doc\output\claude-pricing.json` (USD per 1M tokens; cache read = 0.1x input, cache write = 1.25x input) and write the total into `total_usd`.

### Codex

Read the last `event_msg` with `payload.type == "token_count"` in the session rollout under `%USERPROFILE%\.codex\sessions\YYYY\MM\DD\`; `payload.info.total_token_usage` is cumulative — do not sum snapshots. Store `cached_input_tokens` in `cache_read_tokens`, `0` in `cache_write_tokens`, and leave `total_usd` blank unless the model maps unambiguously to a publicly priced API model.

### Copilot (VS Code)

Copilot bills in **premium request credits**, not tokens, and does not expose a cache-read/cache-write split. Sources:

- **Per-request usage:** `%APPDATA%\Code\User\workspaceStorage\<workspace-hash>\chatSessions\<session-id>.jsonl`. This file is an append-only delta log, so replay every line and key request objects by `requestId`, keeping the last version of each. Fields on each request: `promptTokens`, `completionTokens`, `copilotCredits`, `modelId`, and `promptTokenDetails` (percent-of-prompt breakdown by System Instructions / Tool Definitions / Messages / Tool Results).
- **Do not use the session store** (`copilot_sessionStoreSql`) for cost. The local SQLite store has no `events` table and no token columns; token-level data exists only when cloud sync (`chat.sessionSync.enabled`) is on.
- Ignore the `main.jsonl` in `GitHub.copilot-chat\debug-logs\<session-id>\`; it records only `session_start` and carries no usage.

Ledger mapping: `model` = the `modelId` seen on the requests (record `copilot/auto` verbatim when that is what is stored — the served model is not recorded per request), `input_tokens` = summed `promptTokens`, `cache_read_tokens` and `cache_write_tokens` = blank (not reported by Copilot), `output_tokens` = summed `completionTokens`, `total_usd` = **always blank**. Credits are a quota unit, not dollars: never convert credits to USD and never price Copilot tokens against published API rates.

Report the summed `copilotCredits` as the session's cost figure. Also note these efficiency signals when pronounced: a `promptTokenDetails` prompt dominated by Tool Definitions or Tool Results (points at trimming the tool set or delegating to a subagent), and `promptTokens` climbing turn-over-turn without a compaction (points at `/compact` or a fresh chat).

## Output

Print exactly: the report file path on one line, then `sources: N receipts`. On Copilot, add a third line `credits: <summed copilotCredits>` (omit the line if usage could not be read). In headless mode this is what the wrapper log captures.
