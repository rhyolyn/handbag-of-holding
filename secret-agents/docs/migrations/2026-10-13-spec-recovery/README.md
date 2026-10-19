# Skill Migration Repair — 2026-10-13

> The [later live consolidation](../2026-10-13-live-consolidation/README.md) completes the harness and automation work deferred in this historical report. The verifier now uses preserved archives by default; pass `--original-checkout <path>` only when requesting an additional comparison to a retained checkout.

The initial consolidation used an incomplete Obsidian copy. It replaced the intended post-H1 metadata and generated aliases with a different frontmatter schema, reversed the preflight alias relationship, and documented code/resources as missing. The recovered [integration design](../../specs/2026-10-10-skills-library-integration-design.md) and the untouched `C:/git/handbag-of-holding` checkout supplied the intended model and missing implementation.

## Repaired result

- **22 canonical workflows and 30 generated aliases.** The original 19 workflows and their stable shorthands are restored, with the three unique Worky checkin workflows retained. See [TOC](../../../skills/TOC.md) and [usage guide](../../../skills/README.md).
- Canonical frontmatter uses discovery fields. The post-H1 `Category / Short / Updated / Aliases` line owns categorization and alias metadata. Generated forwarders carry their own matching names and ownership markers.
- `ready-player-one` is canonical; `prpo` and `agent-preflight` forward to it. Every TOC entry shows the callable canonical command followed by its preferred shorthand in parentheses. Compatibility names are secondary notes.
- Restored source, tests, Python configuration, catalog/renderer scripts, reset helper, model-routing/pricing snapshots and skill UI metadata that were present in the recovery source.
- Query, README maintenance and installer update use the same catalog. Query help exits before scanning. Installer instructions select a canonical workflow plus its aliases, preflight every destination, and link each name to its matching source directory.
- Preserved Worky's Jira Epic-parent instructions, report-vault routing, three checkin workflows, Scout guidance and annual Perforce review behavior. The original combined annual evidence workflow remains available explicitly via `year YYYY evidence combined`.
- Corrected inherited generator defects encountered during verification: quoted descriptions, canonical date/hash publication, stable generation dates, generated-alias drift checks, cross-kind name collisions, ordered shorthand initials, misplaced/invalid metadata and unsafe alias names. Catalog checks also detect date-only source edits without mutation.

The original source catalog was used again as the semantic comparison baseline after fixing date publication. This ensures migration-edited bodies have the recovery date instead of retaining dates recorded by the earlier faulty update. [Merge decisions](merge-decisions.md) document the canonical choices.

## Preservation and scope

[Before-recovery ZIP](before-recovery.zip) and [manifest](manifest.json) preserve 181 files from the recovery source and pre-repair vault. All 118 archived recovery-source files still match the original checkout byte for byte. The [initial migration archive](../2026-10-13-worky-agent/original-trees.zip) retains its 61 originals, including all 34 Worky Agent files; its hidden retired tree remains unchanged.

Superseded hand-authored aliases and the former preflight body were moved into `.superseded-directories/` before generation. A later check found only empty directory shells under a reappeared `worky/Agent`; these were preserved in `.resurfaced-worky-tree/`. No files were found in that reappeared tree. Both `worky/Agent` and `worky/Agents` are absent at final verification, and `worky/AGENTS.md` retains the approved pointer.

The initial migration report, plan and verifier are marked historical. Their old schema and missing-resource claims do not describe the repaired library. The old verifier entry point delegates to this recovery audit; its original contents remain in `verify-initial-migration.ps1.historical`.

No machine-level adapters, user skill installations, scheduled tasks, or other Worky consumers were changed. Live harness installation and external integrations were not executed. Pricing/model snapshots retain their normal freshness requirements. Worky data and templates remain in Worky. See [remaining scope](../../../runbooks/migration-gaps.md).

## Verification

The repository gate passed in its documented order:

1. `python -m mypy` — 31 source files, no issues.
2. `python -m ruff check src tests skills/update-model-routing/scripts skills/query-all-skills/scripts` — passed.
3. `python -m ruff format --check src tests skills/update-model-routing/scripts skills/query-all-skills/scripts` — 31 files already formatted.
4. `python -m pytest --tb=short -q` — **168 passed**, no skips.

Catalog `check` and the README renderer/guard pass. The read-only [preservation verifier](verify-recovery.ps1) checks both archives, original checkout hashes, Worky removal/pointer, all 52 YAML headers, canonical hashes, generated aliases, TOC names/shorthands and rendered HTML. Run it from any working directory with Python, PyYAML and Markdown available. Results are recorded in [verification.json](verification.json).

Cold and warm query output matched. Across ten warm runs, median query time was **78.589 ms**, excluding Python startup; the instrumented warm invocation read only its local cache, `catalog.json` and `TOC.md`, with no skill-body reads or recursive traversal. See [query measurements](query-verification.json). Probe caches were kept inside this audit, without changing the user's shared cache.

Independent review confirmed preservation, canonical/alias direction, metadata, TOC, query help, installer link destinations and validation fixes. It reported no remaining repair blockers. The tests exercise temporary fixtures; their success is not a claim that live harness discovery paths have been migrated.
