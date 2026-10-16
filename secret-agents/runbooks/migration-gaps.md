# Migration Status

## Categorized skills library

The skills library is authored under manifest-declared collections. Every
canonical workflow has one source at
`skills/<collection>/<canonical-name>/SKILL.md`; `skills/_generated/` is a
catalog-owned flat projection for harness installation. The catalog validates
the layout, publishes the projection, and owns `catalog.json` and `TOC.md`.

The repository verifies this migration with catalog publication and drift
checks, temporary installer destinations, documentation-renderer tests, the
Python quality gate, and the recovery audit. The checks do not mutate live
harness directories.

## Live-adapter follow-up

Live harness links are intentionally outside this migration batch. Once the
repository checks are green, a user may explicitly authorize reconciliation:

```text
/install-skills --update --harness all --vault-root ~/obsidian
```

That operation must be run only after the user authorizes it for the current
machine. It should link each canonical name to its matching generated
projection and preserve foreign or conflicting destination entries.

## Recovery boundaries

The earlier vault-recovery archives remain evidence, not authored sources.
Use [the recovery audit](../docs/migrations/2026-10-13-spec-recovery/README.md)
when validating restoration claims. Worky reports and templates remain in the
Worky data vault and are resolved through
[worky-vault-paths.md](worky-vault-paths.md).
