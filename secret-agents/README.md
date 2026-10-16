# Secret Agents

`secret-agents` is the maintained source for shared agent guidance, skills,
runbooks, source code, and tests in the Handbag of Holding Obsidian vault.
Obsidian Sync is authoritative. Git may provide history or backup transport,
but it is not the authoring workflow.

The default location is `~/obsidian/handbag-of-holding/secret-agents` on every
platform. Explicit source arguments take precedence over `SECRET_AGENTS_ROOT`,
which takes precedence over that default. A missing source is an error; tools
never fall back to their working directory or an installed adapter.

## Library map

Canonical workflows are authored in one manifest-declared collection. The
generated flat projection is the only installation surface.

| Collection | Workflows | Purpose |
| --- | ---: | --- |
| [Agent Workflow](skills/agent-workflow/README.md) | 2 | Planning and execution workflows for agents. |
| [Code Quality](skills/code-quality/README.md) | 5 | Architecture, error handling, testing, and quality gates. |
| [Maintenance](skills/maintenance/README.md) | 2 | Library and model-maintenance workflows. |
| [Skill Authoring](skills/skill-authoring/README.md) | 5 | Creating, finding, installing, and maintaining skills. |
| [Unreal](skills/unreal/README.md) | 3 | Unreal Engine build, coverage, and release workflows. |
| [Work Tracking](skills/work-tracking/README.md) | 8 | Check-in, Jira, reporting, and work-receipt workflows. |

The [collection manifest](skills/collections.json) defines this order and
identity. The generated [catalog](skills/catalog.json) maps every canonical
name to both its source path and `skills/_generated/<canonical-name>`
projection. [TOC.md](skills/TOC.md) and [the skills guide](skills/README.md)
are generated/catalog-backed discovery aids.

## Ownership and layout

- A canonical source is exactly `skills/<collection>/<canonical-name>/SKILL.md`.
  Edit that file only after reading this README, its collection README, and the
  canonical skill itself.
- `skills/_generated/` is catalog-owned. It contains thin installable adapters;
  never edit an adapter by hand.
- The catalog owner updates `skills/catalog.json`, `skills/TOC.md`,
  `skills/_generated/`, canonical `Updated` dates, and its stat cache.
- Harness mixing directories contain per-name links to projection directories,
  not links to nested canonical sources.

## Common workflows

Find a workflow by reading [TOC.md](skills/TOC.md) or invoking
`/query-all-skills`. To add, revise, or move a workflow, read the applicable
collection README and use the canonical source plus the catalog owner:

```powershell
python skills/skill-authoring/query-all-skills/scripts/catalog.py update --skills-root skills
python skills/skill-authoring/query-all-skills/scripts/catalog.py check --skills-root skills
python skills/skill-authoring/update-skills-readme/scripts/render_html.py --readme skills/README.md --skills-root skills
```

Installers select canonical names only and link each selected name to its
catalog projection. See [install-skills](skills/skill-authoring/install-skills/SKILL.md)
and the [harness setup runbook](runbooks/harness-setup/harness-setup.md).

## Recovery and handoff

On a new machine, sync the vault, validate `.agent-root.json`, run the catalog
check above, then reconcile harness links only with explicit authorization.
The recovery audit and historical context are documented in
[migration-gaps.md](runbooks/migration-gaps.md) and
[the migration audit](docs/migrations/2026-10-13-spec-recovery/README.md).

For repository rules, read [AGENTS.md](AGENTS.md). For the complete usage
guide, read [skills/README.md](skills/README.md) and its generated
[HTML rendering](skills/README.html).
