# Worky Agent Consolidation — 2026-10-13

> **Historical record — superseded by the [spec recovery](../2026-10-13-spec-recovery/README.md).** The initial migration used an incomplete copy. Its metadata schema, alias direction/counts, missing-resource claims and structural verification describe that initial result, not the current library. The restored design uses post-H1 headers and catalog-generated aliases.

Canonical destination: `handbag-of-holding/secret-agents`. Source: `C:\Users\rhyol\obsidian\worky\Agent`. Worky retains only a root `AGENTS.md` pointer; external adapters and other Worky consumers are reserved for phase two.

## Preservation

- [Original trees ZIP](original-trees.zip) contains all 34 source files, original destination files, and directory entries. The migration plan was also captured. This is recovery evidence outside the discoverable skills tree, not another maintained skill source.
- [Manifest](manifest.json) records every original file's SHA-256, size, archive member, and each Worky file's canonical destination.
- The archive was read back and every original-file checksum verified before canonical edits. Source checksums must still match immediately before deletion.
- Historical plans, specs, old guidance, and the verbose runbook backup remain historical records; original paths in them describe the old workspace.
- Automatic approval review rejected recursive deletion with `blocked by policy` and no additional reason. The verified source was instead moved to `.retired-worky-tree/` beside this document, and its files were marked read-only. This hidden recovery snapshot is outside `skills/`; it is historical evidence, not an editable or discoverable skill source. `worky/Agent` is absent.

To recover an original, locate its `archive_member` in the manifest and extract that member to an explicitly selected recovery directory. Do not extract it over the canonical collection without reviewing the merged changes.

## Merge decisions

| Worky content | Canonical disposition |
|---|---|
| `architecture-guards` | Body retained as `clean-code-architecture-guards`; legacy name forwards directly. |
| `ready-player-one` | Body retained as `agent-preflight`; existing fun-name alias retained. |
| `work-receipt-create` | Body retained as `report-receipt`; legacy name forwards directly. |
| `status-report-create` | Body retained as `report-status`; legacy name forwards directly. |
| `reset-unreal-build-environment` | Body retained as `unreal-reset-build-env`; legacy name forwards directly. |
| `ugs-pcb-release` | Body retained as `unreal-ugs-release`; legacy name forwards directly. |
| `jira-human-ticket-create` | Merged Worky's additional Epic-parent object syntax, examples, verification, and batch guidance. |
| `report-rollup` | Preserved Worky's newer Perforce annual-review workflow, annual living-document updates and output path; kept monthly status-report behavior. Corrected the source sentence that suggested feeding monthly outputs into their own inputs. |
| `AGENTS.md` | Preserved the newer destination guidance. Unique Scout commands and macro guidance moved to `runbooks/scout-project-guidance.md`. Canonical root, header convention, data-vault routing, and missing-skill status updated. |
| `AGENTS-v1.md`, `HUMANS.md`, duplicate runbooks | Retained destination versions; substantive content was equivalent after names/line endings. Exact original variants remain archived. |
| Four July plan/spec documents | Copied intact to the matching `docs/superpowers` locations. |
| Checkin skills, Mac coverage, unit tests, query/install skills, README maintenance | Migrated into direct-child skill folders with category/kind metadata. |
| `qas`, `rut`, `jira-ht` | Replaced duplicated alias procedures with direct forwarding, preserving flags and help behavior. |
| `install-skills` | Reconciled its copy-based instructions with handbag's link-only ownership model. Flags retained; target must be resolved explicitly; existing copies are conflicts, not overwrite targets. Original procedure archived. |
| Source skills README | Its unique new-skill sections/reviews were folded into the regenerated catalog. Both complete original catalogs, including historical reviews and cross-cutting analyses, remain in the ZIP. |

Every discoverable skill now has `name`, quoted `description`, `metadata.category`, and `metadata.kind`. Alias headers also contain `metadata.alias_of`. The catalog contains all 20 canonical skills and 9 aliases.

## Scope and missing resources

The inventories found no source code or test files to move: the destination had empty `src` and `tests` directories, and Worky Agent had neither. Empty directory shells are retained. Several referenced helpers and two skill bodies were already absent. See [the gap register](../../../runbooks/migration-gaps.md); no external checkout was searched to fill those gaps.

Worky report and Jira-template paths now resolve through [one data-vault reference](../../../runbooks/worky-vault-paths.md). Reports, templates, project files, and harness settings outside the approved scope were not read or migrated.

## Verification

Final preservation, catalog, alias, link, and source-removal results are recorded in [verification.json](verification.json). Re-run [verify-migration.ps1](verify-migration.ps1) from `C:\Users\rhyol\obsidian` with Python, PyYAML, and Markdown available. This is structural migration verification; it does not assert that absent helpers or external integrations are operational.

Independent review verified the original archive, semantic merges, headers, alias routing, catalog coverage, and Worky data paths. It caught missing invocation fields on `qas` and `rut`; both were restored and rechecked. A read-only query trace produced 20 canonical skills with 9 grouped aliases, and a rollup path trace resolved to the original Worky data vault. No remaining correctness findings were reported.
