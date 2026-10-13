---
name: query-all-skills
description: Use when the user asks what skills are available, which agents or slash commands are loaded, or wants a summary of what each skill does.
---

# Query All Skills

**Category:** Query & Discovery · **Short:** qas · **Updated:** 2026-10-10

List all available skills with their descriptions and shorthands, grouped by category.

## Procedure

### Step 1 — Invoke the catalog

```bash
SKILL_DIR="<directory containing this SKILL.md>"
python3 "$SKILL_DIR/scripts/catalog.py" show --skills-root "$SKILL_DIR/.."
```

The catalog prints a TOC grouped by category: shorthand, canonical name, and one-line description for each skill. Generated aliases (shorthands and compat aliases) are omitted from the listing — only canonical skills appear.

`--target <dir>` is accepted as an alias for `--skills-root <dir>` for backward compatibility.

### Step 2 — Print the usage hint

Immediately after the TOC output, print verbatim:

```
To see how to use any skill, run it with --help (most skills support this):
  /<skill-name> --help
```
