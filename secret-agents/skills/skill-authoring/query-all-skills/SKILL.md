---
name: query-all-skills
description: List canonical skills published in the shared catalog.
---

# Query All Skills

**Category:** Query & Discovery · **Updated:** 2026-10-16

List canonical workflows and their descriptions from the catalog. Canonical
names are the only invocation and installation names.

## Usage

```text
/query-all-skills [--target <skills-directory>]
```

Resolve the agent root through the [harness setup runbook](../../../runbooks/harness-setup/harness-setup.md).
Run the catalog owner at:

```bash
python3 "$AGENT_ROOT/skills/skill-authoring/query-all-skills/scripts/catalog.py" show --skills-root "$SKILLS_ROOT"
```

The catalog presents canonical entries grouped by their manifest collections
and categories. It reads its published data rather than traversing harness
directories or generated adapters. If the catalog is missing or stale, report
its diagnostic and direct the caller to the catalog update command.
