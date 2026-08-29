---
name: update-model-routing
description: Use when model-routing.json may be stale, exact Codex or Claude model IDs need verification, or a plan needs current model profiles.
---

# Update Model Routing

Verify and, only when needed, refresh the centralized `model-routing.json` reference. Model IDs
are volatile; never assert them from memory. The deterministic checker decides staleness — you do
not eyeball dates.

## 1. Check first, always

Run the deterministic checker from the canonical root:

```
python skills/update-model-routing/scripts/check_staleness.py --reference model-routing.json
```

It prints `CURRENT` or `STALE` with `last_verified`, `age_days`, and `stale_after_days`, and exits
`0` (current), `2` (invalid), or `3` (stale). Report that line verbatim.

**If the result is `CURRENT`, stop here and report it** — unless the user explicitly asked you to
refresh. Do not touch the file when it is current and no refresh was requested.

## 2. Refresh only from authoritative sources

Refresh when the checker reports `STALE`, or when the user explicitly requests it. Gather current
model IDs live — never from recollection:

- **Codex / OpenAI IDs:** fetch from the `openai-docs` source recorded in `sources.codex`.
- **Claude IDs:** fetch only from `platform.claude.com` (`sources.claude`). No other host is
  authoritative for Claude.

Verify the exact model ID strings and the supported `reasoning`/`effort` values for each profile.

## 3. Refuse partial updates

If authoritative evidence for **either** provider is unavailable (page down, blocked, ambiguous),
make **no** model-ID changes to **either** provider. An update sourced from memory or a non-official
page is not permitted, and a half-updated reference is worse than an honestly stale one. Report the
blocker and leave the file unchanged.

## 4. Apply the minimal change

When both providers are confirmed:

- Edit only `model-routing.json`.
- Update the changed model IDs and set `last_verified` to today's date.
- Preserve the profile names (`high-risk`, `balanced`, `routine`, `economy`), the schema, and
  `stale_after_days`.

## 5. Re-verify and report

Rerun the checker (expect `CURRENT`) and the routing tests:

```
python skills/update-model-routing/scripts/check_staleness.py --reference model-routing.json
python -m pytest tests/test_model_routing.py -q
```

Report the new age, the source URLs consulted, every model-ID substitution made, and the profiles
that were left unchanged.
