# Installer Domain and CLI Redesign

**Date:** 2026-08-29

**Status:** Awaiting written-spec review

**Supersedes:** The tentative vocabulary and CLI directions in `2026-08-29-installer-vocabulary-and-cli-redesign-handoff.md`

## Summary

Batch 3 implemented transactional install and uninstall, ownership receipts, rollback, and a three-command CLI. Its behavior is broadly correct and its existing 123 tests pass, but the implementation does not meet the repository's readability and state-ownership standards. Generic terms such as `Projection`, `Finding`, and `ActionKind` obscure the domain; `_Session` hides command-specific coupling; commands print and select exit codes throughout their control flow; and a parent mapping is sometimes attached to a child skill link, forcing receipt construction to compensate for a model that is not telling the truth.

The redesign replaces the abstract vocabulary with source-to-destination mappings, exact path status records, and typed filesystem changes. Each command returns a `CommandResult`, and one `Console` owns stdout, stderr, stable text, and exit-code mapping. Expected command outcomes are values; unexpected mutation failures remain exceptions. The refactor preserves existing public behavior except for explicitly identified defects whose current behavior violates the approved safety and failure contracts.

## Existing instruction-file behavior

The installer manages two kinds of canonical content:

- `SkillsMapping` makes the canonical `skills` collection available in a harness's personal skills directory. Depending on the destination, this may be one directory link or one link per canonical skill.
- `InstructionsMapping` makes the canonical `AGENTS.md` available at a harness-specific instruction path:
  - Codex: `.codex/AGENTS.md`
  - Claude: `.claude/CLAUDE.md`
  - Copilot: `.copilot/copilot-instructions.md`

`InstructionsMapping` names the file's role at the destination. The implementation does not use `GuidanceMapping`; “guidance” does not identify a concrete artifact or operation.

## Goals

- Make the install, check, and uninstall flows readable without explanatory comments.
- Give every model one domain meaning and one owner.
- Expose each command's actual dependencies instead of aggregating their union in a context bag.
- Preserve the transactional receipt and rollback guarantees.
- Make illegal change shapes unrepresentable rather than checking `kind` plus nullable fields at runtime.
- Give one boundary sole ownership of CLI text, streams, and exit codes.
- Correct the verified managed-home, backup, partial-link, uninstall-coupling, and cancellation defects.
- Preserve receipt schema version 1 compatibility and existing output unless this spec explicitly identifies a correction.

## Non-goals

- Adding commands or flags.
- Changing harness discovery locations.
- Adding copy or hard-link fallbacks.
- Building a general installation framework or a god-object `Installer` service.
- Rewriting the working link and transaction backends merely to obtain smaller files.
- Renaming serialized receipt fields solely to match new in-process names.
- Changing root resolution, catalog validation rules, or harness selection behavior beyond removing dependencies from commands that do not consume them.

## Vocabulary

### Desired mappings

`InstallMapping` is a type alias, not another data container:

```python
InstallMapping = InstructionsMapping | SkillsMapping
```

Both mappings state where canonical content comes from, where a harness discovers it, and which harnesses consume that destination. Their concrete types own the invariants currently represented by `ProjectionKind` and `is_directory`.

`InstructionsMapping` contains a canonical instruction file and a harness instruction file. `SkillsMapping` contains the canonical skills directory and a harness skills directory. The plural `Skills` is intentional: the mapping concerns the collection, even when planning expands it into individual skill links.

Rejected alternatives:

- `Projection` is a mathematical and graphics term that requires translation before use.
- `Mirror` suggests synchronization or a refreshed copy and becomes inaccurate when a skills directory is merged one skill at a time.
- `InstallTarget` is ambiguous between the installed content and its destination.
- `Placement` emphasizes the destination while hiding the source-to-destination relationship.
- `GuidanceMapping` does not identify the instruction file being installed.

### Current filesystem state

Install planning produces `PathStatus` values. A status reports the current filesystem state of one exact destination involved in an install mapping. It contains the path, an `InstallState`, and the exact desired link metadata needed to explain or repair that path.

Install states include the current meanings of correct, missing, stale link, broken link, compatible skills directory, conflicting path, and skill-name collision. A state that can be resolved by an approved backup is distinct from an unresolved conflict; a separate `blocking` boolean must not contradict the state.

Uninstall planning produces `RemovalStatus` values with a `RemovalState`. Removal states answer different questions: whether a path is owned, missing, shared with an unselected harness, foreign, backed by a missing or modified file, or an installer-created parent that must be preserved.

`Observation` and `Finding` are rejected because neither names the subject being reported. `PathStatus` and `RemovalStatus` make the subject and consumer reaction explicit.

### Plans and changes

`InstallPlan` and `UninstallPlan` remain. A plan is exactly what these values represent: a read-only assessment plus an ordered set of changes that may be applied as one transaction.

Generic action records and action-kind enums are replaced with typed changes:

- Install: `CreateLink`, `ReplaceLink`, and `BackupFile`.
- Uninstall: `RemoveLink`, `RestoreFile`, `RemoveDirectory`, `WriteReceipt`, and `DeleteReceipt`.

Each type carries only the fields its operation requires. There is no nullable `source`, redundant `is_directory` plus content kind, or defensive unsupported-kind branch. A link-producing change carries the exact link ownership metadata that a successful execution adds to the receipt. Receipt construction must not recover that metadata indirectly from a status keyed by path.

### Receipts and execution results

`ReceiptProjection` becomes `OwnedLink`; `ReceiptBackup` becomes `OwnedBackup`. These names describe why the records exist: they are the mutations a later uninstall may reverse. `InstallReceipt` remains.

The version 1 JSON keys and values remain readable and writable, including the legacy serialized `"projections"` collection and `"guidance"` value. Serialization is a compatibility boundary; it translates those persisted names to the approved in-process model. Renaming Python types does not invalidate existing receipts.

`ExecutionEvent` becomes `AppliedChange`. The generic `ExecutionReport` is split into `InstallResult` and `UninstallResult` so absence of a receipt or events never has to be decoded as an implicit `not-installed` outcome. Receipt creation, replacement, deletion, or no change is explicit in the appropriate result.

## Ownership and module boundaries

`models.py` retains only genuinely shared core values such as `Harness`, `AgentRoot`, and `SkillDescriptor`. Domain values live beside the behavior that owns them:

- `harness_profiles.py`: `InstructionsMapping`, `SkillsMapping`, and mapping construction.
- `planning.py`: path/removal statuses, plans, and typed changes.
- `receipts.py`: `OwnedLink`, `OwnedBackup`, `InstallReceipt`, and schema translation.
- `executor.py`: private transaction journals, `AppliedChange`, `InstallResult`, and `UninstallResult`.
- `commands.py`: command orchestration and `CommandResult`.
- `console.py`: `Console`, stable output text, stream selection, and `ExitCode` mapping.
- `cli.py`: argument parsing, dependency construction, command dispatch, and the process-return boundary.

This layout is ownership-driven rather than one file per type. Closely related small values may remain together when splitting them would make the flow harder to scan.

`_Session` is removed. It currently holds the union of every command's inputs and derived state, then hides backend construction and install-only catalog work behind properties. Each command instead receives only what it uses:

- `check`: resolved root, selected harnesses, home, catalog, and clock.
- `install`: the check inputs plus link backend, receipt storage, and install options.
- `uninstall`: resolved root identity, selected harnesses, home, link backend, and receipt storage. It does not load or validate the skill catalog and does not build install mappings.

Wide command signatures remain visible until a cohesive owner—not a parameter-count target—justifies a class.

## CLI result and presentation boundary

Command functions do not print and do not return integer exit codes. They return a `CommandResult` containing:

- a `CommandStatus` such as `OK`, `NOT_INSTALLED`, `BLOCKED`, `FAILED`, or `INVALID_INPUT`;
- resolved root and harness selection when available;
- path or removal statuses to report;
- applied changes to report;
- an optional semantic diagnostic with structured context.

`Console` is the only unit that converts `CommandResult` into text, chooses stdout or stderr, and maps `CommandStatus` to `ExitCode`. Its public operation reads as `console.present(result) -> int`.

The top-level flow is:

```python
def main(...) -> int:
    request = parse_command(argv)
    result = run_command(request, dependencies)
    return console.present(result)
```

Argparse remains responsible for standard usage and help formatting. All successfully parsed commands use the single result/presentation path.

## Error contract

Expected states are values:

- current installation;
- remediation required by `check`;
- dry-run preview;
- blocked install or uninstall;
- no receipt / not installed;
- successful install or uninstall.

Unexpected mutation failures remain Python exceptions. `ExecutionError` remains the public family because it is concise and follows Python convention. It gains explicit `install` or `uninstall` operation context so its stable diagnostic never reports an uninstall as an install failure. It preserves the original cause, rollback failures, and manually recoverable paths.

Programmer errors, including applying a blocked plan or passing a change to the wrong executor, fail fast and are not converted to command results.

Cancellation is explicit. The executor rolls back after `KeyboardInterrupt`, `SystemExit`, or `GeneratorExit`, then re-raises the original cancellation unchanged when rollback succeeds. If rollback leaves manually recoverable paths, those paths are attached to the cancellation diagnostic before it is re-raised. The CLI does not translate cancellation into `EXECUTION_FAILED`.

The failure mapping remains:

| Condition | Representation | CLI result |
|---|---|---|
| Invalid arguments, root, or install/check catalog | Native parser or semantic input error | `INVALID_INPUT` / 2 |
| Missing or stale paths reported by `check` | `CommandResult` | `BLOCKED` / 3 |
| Conflict, invalid receipt, or missing link capability | Semantic error converted once at command boundary | `BLOCKED` / 3 |
| Backup destination occupied before reservation | Semantic error before user-content mutation | `BLOCKED` / 3 |
| Mutation or rollback failure | `ExecutionError` converted once at command boundary | `FAILED` / 4 |
| Programmer error | Native exception | No translation |
| Cancellation | Native cancellation after rollback | No translation |

## Safety corrections

These corrections are intentional behavior changes, not incidental refactoring.

### Managed-home boundary

Receipt parsing and uninstall planning share one containment implementation. It normalizes the configured home, rejects lexical traversal such as `home/../victim`, and validates the resolved parent of each managed destination against the resolved home. It does not resolve the final link itself because an installed link intentionally resolves to the canonical root outside home. The same boundary is checked while loading a receipt and immediately before planning destructive work.

Tests cover `..`, mixed normalization, and a parent directory that is itself a link outside home. An escaping path blocks all uninstall changes.

### Backup destination ownership

Planning chooses the first unused deterministic timestamped backup name. Execution reserves that exact destination with exclusive creation before moving the original file. If another process or file occupies it, execution stops before changing the original. No operation uses an overwrite-capable move against a path it has not exclusively reserved.

Losing the reservation race is a blocked expected outcome, not an execution failure, because no user content has changed.

Rollback removes an unused reservation or restores the original from the completed backup as appropriate. Existing backup bytes are never replaced.

### Atomic link-backend contract

`LinkBackend.create_file_link` and `create_directory_link` become atomic from the executor's perspective. If creation succeeds but verification fails, the backend removes the partial link before raising. If that cleanup also fails, the error identifies the recoverable path explicitly.

The executor continues to journal a completed link creation only after the backend returns successfully. Tests inject failure both before mutation and after creation during verification.

### Command-specific setup

Uninstall resolves only the canonical root identity and receipt-owned state. A missing or malformed `SKILL.md` cannot prevent receipt-based cleanup. Catalog validation remains mandatory for install and check because those commands consume the current skills collection.

## Compatibility

Except for the safety and diagnostic corrections listed above:

- command names, arguments, defaults, stdout rows, stderr ownership, and exit codes remain unchanged;
- receipt schema version 1 remains compatible;
- successful and blocked operations preserve their current mutation boundaries;
- install and uninstall remain idempotent;
- existing imports needed by the process entrypoints remain stable or receive narrow compatibility re-exports during the migration.

The prior design's term “projection” is superseded by this spec for installer implementation. Historical text need not be rewritten merely to erase the old word; active documentation and code use mappings.

## Verification

Implementation follows red-green tests for each slice. In addition to preserving the existing suite, acceptance coverage includes:

- receipt paths with lexical traversal are rejected;
- managed paths whose parent resolves outside home are rejected;
- an occupied backup path is never overwritten;
- a failure after OS link creation leaves no partial link;
- a failure to clean a partial link reports its recoverable path;
- uninstall succeeds or reports `not-installed` when the current skill catalog is malformed;
- uninstall execution failures name uninstall, not install;
- cancellation rolls back and remains cancellation;
- blocked dry-run and other handled failures retain their documented stream and exit-code behavior;
- `Console` is the only non-argparse owner of result text and exit-code mapping;
- command orchestration contains no `_Session`-style union context;
- receipt round trips remain byte-for-byte deterministic for schema version 1.

The final gate is mypy, Ruff check, Ruff format check, the complete pytest suite, compileall, and `git diff --check` on every supported local target. Cross-platform link behavior remains subject to the existing Windows, Linux, and macOS CI matrix.

## Sequencing

1. Add adversarial tests and correct managed-home containment, backup no-clobber behavior, partial-link cleanup, uninstall catalog independence, cancellation, and operation-aware diagnostics.
2. Introduce mappings and exact status/change types; migrate planning, receipts, and execution without changing CLI output.
3. Introduce command-specific orchestration, `CommandResult`, and `Console`; remove `_Session` and distributed printing/exit-code helpers.
4. Add an architectural check that prevents command modules from printing or importing `ExitCode`, and proves the check detects a planted violation.
5. Run focused tests after each slice and the complete quality gate before integration.

The implementation plan must divide these into reviewable commits and preserve the ability to distinguish safety corrections from behavior-preserving structural changes.
