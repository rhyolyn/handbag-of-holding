---
name: update-skill
description: Revise one canonical skill and republish its catalog-owned artifacts.
---

# Update Skill

**Category:** Skill Management · **Updated:** 2026-10-16

Revise one canonical workflow by its canonical name.

## Procedure

1. Read the root README, then `catalog.json` to resolve the entry's
   `source_path`. Read that collection README and canonical `SKILL.md` before
   changing instructions.
2. Edit only `skills/<source_path>/SKILL.md`. Do not edit an installed adapter
   or any path below `_generated`.
3. Preserve the canonical name and collection unless the requested change is a
   deliberate move with manifest and catalog verification. Keep the post-H1
   `Category / Updated` header format.
4. Run the catalog update and check commands. Then render and verify the skills
   README through `update-skills-readme`.

If the requested name is absent from the catalog, fail before editing. Catalog
publication owns all derived artifacts and reports structural errors with the
canonical source path and remediation command.
