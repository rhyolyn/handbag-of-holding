---
name: update-skills-readme
description: Use when a skill under Agent/skills is added, removed, or edited, when the skills README.md or README.html is missing or stale, or when the user invokes /update-skills-readme (optionally with "review").
---

# Update Skills README

Keep `<skills root>\README.md` and `README.html` in sync with the skill set. The markdown is the source of truth; the HTML is rendered from it and never hand-edited.

## Paths & Model

- Skills root: `<skill base dir>\..` (this skill sits at `<worky root>\Agent\skills\update-skills-readme`).
- Renderer/guard: `<skill base dir>\scripts\render_html.py`.
- Model: Sonnet-class without `review`; frontier-class when `review` is passed — reviews are judgment, not transcription.

## Arguments

- *(none)* — factual refresh: inventory, parameters, call formats, examples, TOC, coverage matrix. Existing per-skill **Architect's review.** blocks are preserved verbatim.
- `review` — additionally regenerate every Architect's review (strengths, weaknesses, improvements) from a full read of each SKILL.md.

## Steps

1. **Inventory.** Every directory under the skills root containing a `SKILL.md`. Read each skill's frontmatter; read full bodies for skills that are new or changed since the README's generated date (all of them under `review`).
2. **Regenerate README.md** keeping its section contract: intro with generated date, Table of Contents, "How skills are wired and invoked", "Skill inventory" table, one `### <skill-name>` section per skill (What it does / When to use / Parameters / Examples for Claude, Codex, and Copilot / Architect's review), "Architect's overview" (harness coverage matrix, skill gaps, token-costly mistakes), "Maintaining this document".
   - Without `review`: copy each existing **Architect's review.** block unchanged; a skill with no existing review gets `> Review pending — rerun with "review".`
   - Verify factual claims (paths, wiring, file existence) with checks before asserting them; never carry a claim forward untested under `review`.
3. **Render + verify:** `uv run <skill base dir>\scripts\render_html.py`. The script exits 2 with named problems when a skill directory has no `### <name>` section or `#<name>` link, when any anchor is dead, or when it scans zero skills. Fix the README and re-run.
4. **Output.** Print exactly: the README.md path, the README.html path, then the script's `verified:` line.

## Common Mistakes

- Editing README.html directly — the next render silently discards the edit.
- Rendering before updating the markdown — the guard checks structure, not freshness; it will green stale prose.
- Running `review` on a small model — reviews come out generic praise; preserve them instead.
- Treating a guard failure as an obstacle — "missing section" means a skill is undocumented; document it, never weaken the script's checks to get to green.
