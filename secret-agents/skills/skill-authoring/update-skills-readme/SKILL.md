---
name: update-skills-readme
description: Regenerate and verify the canonical skills README and HTML guide.
---

# Update Skills README

**Category:** Skill Management · **Updated:** 2026-10-16

Keep `skills/README.md` and its generated `README.html` aligned with the
manifest and schema-v2 catalog.

## Procedure

1. Run the catalog owner update and check commands from the agent root.
2. Read `collections.json` and `catalog.json` to inventory canonical entries.
   Link every human-facing source reference to its collection-relative
   `source_path`; do not inventory `_generated` adapters as authored skills.
3. Ensure the Markdown guide has a link and `### <canonical-name>` section for
   every catalog entry, with no extra installation-name columns or fields.
4. Render and verify the HTML only through:

   ```powershell
   python skills/skill-authoring/update-skills-readme/scripts/render_html.py --readme skills/README.md --skills-root skills
   ```

The renderer refuses an empty inventory or a manifest/catalog/source mismatch.
Do not edit `README.html` directly.
