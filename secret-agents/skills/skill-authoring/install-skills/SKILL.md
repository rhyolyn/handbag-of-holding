---
name: install-skills
description: Install catalog-published skills into harness mixing directories.
---

# Install Skills

**Category:** Skill Management · **Updated:** 2026-10-16

Install only canonical skill names. The installer reads `catalog.json` and
links each selected name to `skills/_generated/<canonical-name>`; canonical
collection sources are never linked directly.

## Inputs

```text
/install-skills [canonical-name ...] [--all] [--update] [--harness <name>] [--target <directory>] [--vault-root <directory>]
```

`--vault-root` defaults to `~/obsidian`. `--target` selects a destination and
is mutually exclusive with `--harness`. A missing requested canonical name or
any destination conflict aborts before the installer creates a link.

## Procedure

1. Resolve `<agent-root>` from `--vault-root`, then `SECRET_AGENTS_ROOT`, then
   the home-relative default. Validate `.agent-root.json`.
2. With `--update`, run the catalog owner at
   `skills/skill-authoring/query-all-skills/scripts/catalog.py update` and
   stop on any error.
3. Read schema-v2 `catalog.json`; select every entry for `--all`, or only the
   exact requested canonical entries. Resolve each source solely through its
   `generated_projection[canonical-name]`.
4. Preflight every destination. Existing correct links are retained; foreign
   entries or links to another target are conflicts. Do not create any link
   until the complete preflight passes.
5. Create only missing directory links to their projection paths and report
   each created or already-correct destination.

Do not run this against user-home harness directories without explicit user
authorization. See the [harness setup runbook](../../../runbooks/harness-setup/harness-setup.md)
for supported mixing directories.
