---
name: write-skill
description: Create a canonical skill in a declared collection and publish it through the catalog.
---

# Write Skill

**Category:** Skill Management · **Updated:** 2026-10-16

Create one canonical workflow without hand-authoring derived artifacts.

## Procedure

1. Read the root README, choose a declared collection from `collections.json`,
   then read that collection's README and nearby canonical skills.
2. Refresh and inspect `catalog.json`; reject an already-used canonical name.
3. Create only `skills/<collection>/<canonical-name>/SKILL.md`. Use portable
   `name` and trigger-focused `description` frontmatter, an H1, then
   `**Category:** <category> · **Updated:** <YYYY-MM-DD>`.
4. Write the workflow's non-obvious context, failure behavior, and verification
   steps. Do not create or modify the catalog, TOC, projection, or README HTML
   by hand.
5. Run the catalog update and check commands, then update the skills README
   through its owner. Report any structural failure with the source path and
   remediation command.

Collection identity comes from the manifest, while category remains workflow
metadata. Do not introduce a collection outside `collections.json`.
