# Installer Domain and CLI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the verified installer safety defects and replace the opaque projection/session/CLI model with explicit mappings, path statuses, typed changes, command results, and one console boundary.

**Architecture:** Preserve read-only planning followed by journaled transactional execution. Desired content is represented by `InstructionsMapping | SkillsMapping`; plans contain exact statuses and typed changes; receipts persist owned links and backups; command functions return values; and `Console` alone owns non-argparse output and exit codes.

**Tech Stack:** Python 3.11+ standard library, pytest 9.0.3, mypy 2.3.0 strict mode, Ruff 0.16.1, Git, GitHub CLI.

**Spec:** `secret-agents/docs/superpowers/specs/2026-08-29-installer-domain-and-cli-design.md`

## Global Constraints

- Runtime dependencies remain standard-library only; `requires-python` remains `>=3.11`.
- Preserve command names, arguments, defaults, harness paths, stdout rows, stderr ownership, and exit codes except for the explicit defect corrections in the spec.
- Preserve receipt schema version `1`, deterministic JSON, and compatibility with persisted `"projections"` and `"guidance"` values.
- Do not add copy, hard-link, or silent fallback behavior.
- `InstructionsMapping` means canonical `AGENTS.md` to a harness instruction file. `SkillsMapping` means the canonical skills collection to a harness skills directory. Do not introduce `GuidanceMapping`, `Projection`, or `Mirror` as active implementation vocabulary.
- Expected command outcomes are `CommandResult` values. Mutation failures remain `ExecutionError`; programmer errors and cancellation are not translated.
- Every destructive path is validated against the resolved managed-home boundary immediately before planning or mutation.
- Follow RED/GREEN for every behavior change. A test must fail for the intended reason before its implementation step begins.
- Update this tracked plan's checkbox in the same commit as the code and verification that complete the step or task.
- Do not modify or stage the pre-existing unrelated edits to `AGENTS.md`, `skills/README.md`, `skills/README.html`, `skills/python-quality-gate/SKILL.md`, or `src/secret_agents_setup.egg-info/`.
- Before agent dispatch, verify the recommended model is available. If unavailable, substitute only a same-provider current model at the same or higher capability and record the substitution.

## Model Routing

Recommendations come from `secret-agents/model-routing.json`, last verified `2026-08-28`:

| Profile | Codex | Claude | Use |
|---|---|---|---|
| `high-risk` | `gpt-5.6-sol`, high reasoning | `claude-opus-5`, high effort | Filesystem safety, rollback, receipt compatibility, cross-domain migrations |
| `balanced` | `gpt-5.6-terra`, high reasoning | `claude-sonnet-5`, high effort | Command boundaries, integration, public behavior |
| `routine` | `gpt-5.6-terra`, medium reasoning | `claude-sonnet-5`, medium effort | Mechanical guards, final documentation, delivery |

## Branch and Delivery Contract

Implementation starts from local branch `batch-3-rollback-execution-and-cli`, which contains the approved spec and this plan. The current source worktree has unrelated edits, so execution must use an isolated worktree and a new branch named `batch-3-installer-domain-cli-redesign`.

Batch 1 creates that branch. Batches 2–4 continue on it. After Batch 4 passes, push the branch and open a pull request against `main`; the new PR supersedes the earlier Batch 3 PR rather than layering a partial architecture fix on top of it.

If the branch or proposed worktree path already exists, stop and inspect it. Do not delete, reset, or force-recreate either one.

## File and Responsibility Map

| File | Responsibility after this plan |
|---|---|
| `src/secret_agents_setup/models.py` | Shared core values only: `Harness`, `AgentRoot`, `SkillDescriptor` |
| `src/secret_agents_setup/path_safety.py` | One resolved managed-directory containment rule |
| `src/secret_agents_setup/harness_profiles.py` | `InstructionsMapping`, `SkillsMapping`, `InstallMapping`, deterministic mapping construction |
| `src/secret_agents_setup/planning.py` | Install/removal statuses, typed changes, `InstallPlan`, `UninstallPlan` |
| `src/secret_agents_setup/receipts.py` | `OwnedLink`, `OwnedBackup`, `InstallReceipt`, schema-v1 translation and persistence |
| `src/secret_agents_setup/receipt_errors.py` | Semantic receipt validation errors |
| `src/secret_agents_setup/links.py` | Cross-platform link operations that are atomic from the executor's perspective |
| `src/secret_agents_setup/link_errors.py` | Structured link and partial-cleanup failures |
| `src/secret_agents_setup/executor.py` | Transaction journals, typed change application, `AppliedChange`, install/uninstall results |
| `src/secret_agents_setup/executor_errors.py` | Operation-aware `ExecutionError` and rollback details |
| `src/secret_agents_setup/commands.py` | Command-specific orchestration and `CommandResult` |
| `src/secret_agents_setup/console.py` | Stable text, stdout/stderr selection, and exit-code mapping |
| `src/secret_agents_setup/cli.py` | Argparse, dependency construction, command dispatch, process return |
| `tests/test_path_safety.py` | Direct containment contract and planted traversal cases |
| `tests/test_cli_architecture.py` | Machine-enforced command/presentation boundary with planted violations |
| Existing focused test modules | Behavioral coverage next to the domain they exercise |

---

## Batch 1: Filesystem and Transaction Safety

**Batch routing:** `high-risk` for every task. These changes protect user files and rollback behavior and must land before structural renames obscure the old failure paths.

### Copy/paste handoff

```text
Implement Batch 1 of the Installer Domain and CLI Redesign plan.

Repository root: C:\git\handbag-of-holding
Source branch: batch-3-rollback-execution-and-cli
New branch: batch-3-installer-domain-cli-redesign
Plan: secret-agents/docs/superpowers/plans/2026-08-29-installer-domain-and-cli-redesign.md
Spec: secret-agents/docs/superpowers/specs/2026-08-29-installer-domain-and-cli-design.md

Use superpowers:using-git-worktrees before editing. The source worktree contains unrelated user changes; do not work in it. From the repository root in PowerShell, after the skill's read-only checks, create the isolated branch/worktree without force:

$repoRoot = (git rev-parse --show-toplevel).Trim()
$worktreePath = Join-Path (Split-Path $repoRoot -Parent) 'handbag-of-holding-installer-redesign'
git worktree add -b batch-3-installer-domain-cli-redesign $worktreePath batch-3-rollback-execution-and-cli
Set-Location (Join-Path $worktreePath 'secret-agents')
git status --short --branch

Require a clean new worktree. Install the pinned dev extras with `python -m pip install -e ".[dev]"`, run `python -m pytest --tb=short -q`, and require the inherited 123-test baseline before Task 1.

Model routing: every task uses high-risk — Codex gpt-5.6-sol/high or Claude claude-opus-5/high. Verify availability before dispatch and record any allowed substitution.

Execute Tasks 1–4 with strict RED/GREEN. Update plan checkboxes in each task commit. Stop after Task 4's focused tests and the full Batch 1 pytest suite pass. Report the new branch/worktree, four commits, exact tests, and any substitutions. Do not start Batch 2.
```

### Task 1: Enforce One Managed-Home Boundary

**Model recommendation:** Codex `gpt-5.6-sol` with high reasoning; Claude `claude-opus-5` with high effort (`high-risk`). Path normalization and symlink-parent traversal directly guard destructive uninstall work.

**Files:**
- Create: `secret-agents/src/secret_agents_setup/path_safety.py`
- Modify: `secret-agents/src/secret_agents_setup/receipts.py`
- Modify: `secret-agents/src/secret_agents_setup/planning.py`
- Create: `secret-agents/tests/test_path_safety.py`
- Modify: `secret-agents/tests/test_receipts.py`
- Modify: `secret-agents/tests/test_uninstall.py`

**Interfaces:**
- Produces: `is_path_within(path: Path, root: Path, *, follow_leaf: bool) -> bool`.
- `follow_leaf=False` resolves the candidate's parent but not the final link; install destinations intentionally resolve outside home.
- `follow_leaf=True` resolves the candidate itself; use it for backups, created parents, and canonical receipt sources.
- Receipt errors keep their current public types and messages unless the existing message misidentifies the escaped field.

- [x] **Step 1: Add direct failing traversal tests**

Create `tests/test_path_safety.py` with these cases:

```python
from pathlib import Path

import pytest

from secret_agents_setup.path_safety import is_path_within


def test_lexical_parent_traversal_is_outside(tmp_path: Path) -> None:
    home = (tmp_path / "home").resolve()
    home.mkdir()

    assert not is_path_within(home / ".." / "victim", home, follow_leaf=False)


def test_destination_below_home_is_inside_without_following_leaf(tmp_path: Path) -> None:
    home = (tmp_path / "home").resolve()
    home.mkdir()

    assert is_path_within(home / ".codex" / "AGENTS.md", home, follow_leaf=False)


def test_linked_parent_outside_home_is_rejected(tmp_path: Path) -> None:
    home = (tmp_path / "home").resolve()
    outside = (tmp_path / "outside").resolve()
    home.mkdir()
    outside.mkdir()
    try:
        (home / ".codex").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"host cannot create parent symlink: {exc}")

    assert not is_path_within(home / ".codex" / "AGENTS.md", home, follow_leaf=False)
```

- [x] **Step 2: Add failing receipt and uninstall integration cases**

Extend `test_receipts.py` so a schema-v1 destination containing `home / ".." / "victim"` raises `ReceiptPathOutsideHome`, and a source containing `installed_root / ".." / "foreign"` raises `ReceiptSourceOutsideRoot`. Extend `test_uninstall.py` with a receipt destination below a linked parent and assert `plan.can_apply is False` and `plan.actions == ()` under the current model.

- [x] **Step 3: Run the focused tests and observe RED**

Run:

```text
python -m pytest tests/test_path_safety.py tests/test_receipts.py tests/test_uninstall.py -v
```

Expected: import failure for `path_safety`, followed after test collection is restored by the current lexical `is_relative_to` checks accepting at least the `..` escape.

- [x] **Step 4: Implement the shared containment rule and route both callers through it**

Create the helper with this behavior:

```python
def is_path_within(path: Path, root: Path, *, follow_leaf: bool) -> bool:
    if not path.is_absolute() or not root.is_absolute():
        return False
    resolved_root = root.resolve(strict=False)
    resolved_path = (
        path.resolve(strict=False)
        if follow_leaf
        else path.parent.resolve(strict=False) / path.name
    )
    return resolved_path.is_relative_to(resolved_root)
```

Use it in receipt loading for every destination, source, backup path, and created parent with the leaf policy above. Replace `planning._within_home` with the shared helper and recheck receipt-derived destructive paths during uninstall planning.

- [x] **Step 5: Run focused tests and require GREEN**

Run:

```text
python -m pytest tests/test_path_safety.py tests/test_receipts.py tests/test_uninstall.py -v
```

Expected: PASS, with only the real-parent-link test skipped on hosts that cannot create it.

- [x] **Step 6: Commit Task 1**

Check this task and its completed steps in this plan, then run:

```text
git add -- src/secret_agents_setup/path_safety.py src/secret_agents_setup/receipts.py src/secret_agents_setup/planning.py tests/test_path_safety.py tests/test_receipts.py tests/test_uninstall.py docs/superpowers/plans/2026-08-29-installer-domain-and-cli-redesign.md
git diff --cached --check
git commit -m "fix: enforce managed home boundary"
```

### Task 2: Reserve Backups Without Clobbering Existing Files

**Model recommendation:** Codex `gpt-5.6-sol` with high reasoning; Claude `claude-opus-5` with high effort (`high-risk`). The change replaces overwrite semantics in a user-content path and must preserve rollback.

**Files:**
- Modify: `secret-agents/src/secret_agents_setup/planning.py`
- Modify: `secret-agents/src/secret_agents_setup/executor.py`
- Modify: `secret-agents/src/secret_agents_setup/executor_errors.py`
- Modify: `secret-agents/src/secret_agents_setup/cli.py`
- Modify: `secret-agents/tests/test_planning.py`
- Modify: `secret-agents/tests/test_executor.py`
- Modify: `secret-agents/tests/test_cli.py`

**Interfaces:**
- Produces private `_available_backup_path(original: Path, timestamp: datetime) -> Path`, choosing the unsuffixed timestamped path, then `-2`, `-3`, and so on.
- Produces `BackupPathOccupied(path: Path)`, a semantic pre-mutation error mapped to `BLOCKED` / 3.
- `_InstallRun._backup` exclusively reserves the planned destination before moving the original and never overwrites a path it did not reserve.

- [ ] **Step 1: Write failing planning and execution tests**

Add these contracts:

```python
def test_backup_planning_uses_next_free_suffix(tmp_path: Path) -> None:
    # Arrange the normal timestamped backup before building the plan.
    # Assert the BackupFile action selects "AGENTS.md.backup-20260829-120000-2".


def test_backup_race_never_overwrites_existing_bytes(tmp_path: Path) -> None:
    # Build the plan while its backup destination is free, then create that file.
    # Applying the plan raises BackupPathOccupied, the original is unchanged,
    # the occupied backup bytes are unchanged, and no link or receipt exists.
```

Add a CLI test asserting `BackupPathOccupied` yields `ExitCode.BLOCKED`, prints `result blocked`, reports the occupied path on stderr, and does not print `result failed`.

- [ ] **Step 2: Run the focused tests and observe RED**

Run:

```text
python -m pytest tests/test_planning.py tests/test_executor.py tests/test_cli.py -v
```

Expected: the planner selects the occupied name or `_backup` overwrites it via `os.replace`; `BackupPathOccupied` does not exist.

- [ ] **Step 3: Implement deterministic selection and exclusive reservation**

Use `os.path.lexists` while selecting the deterministic plan destination. In `_backup`, reserve with `os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)` and close the descriptor before replacing the reservation with the original. If reservation fails with `FileExistsError`, raise `BackupPathOccupied` before reading, moving, or linking user content. If the subsequent move fails, remove only the reservation created by this execution before propagating.

Do not use an existence-check followed directly by overwrite-capable `os.replace` without exclusive reservation.

- [ ] **Step 4: Map the pre-mutation race through the current CLI boundary**

Catch `BackupPathOccupied` with the existing blocked/capability group. Do not wrap it in `ExecutionError`; the operation has not started mutating managed state.

- [ ] **Step 5: Run focused tests and require GREEN**

Run:

```text
python -m pytest tests/test_planning.py tests/test_executor.py tests/test_cli.py -v
```

Expected: PASS and both the original file and pre-existing backup bytes remain exact in the race case.

- [ ] **Step 6: Commit Task 2**

```text
git add -- src/secret_agents_setup/planning.py src/secret_agents_setup/executor.py src/secret_agents_setup/executor_errors.py src/secret_agents_setup/cli.py tests/test_planning.py tests/test_executor.py tests/test_cli.py docs/superpowers/plans/2026-08-29-installer-domain-and-cli-redesign.md
git diff --cached --check
git commit -m "fix: reserve conflict backups safely"
```

### Task 3: Make Link Creation Atomic to the Executor

**Model recommendation:** Codex `gpt-5.6-sol` with high reasoning; Claude `claude-opus-5` with high effort (`high-risk`). This task closes the verified create-then-verify rollback hole on multiple operating systems.

**Files:**
- Modify: `secret-agents/src/secret_agents_setup/links.py`
- Modify: `secret-agents/src/secret_agents_setup/link_errors.py`
- Modify: `secret-agents/src/secret_agents_setup/executor.py`
- Modify: `secret-agents/tests/test_links.py`
- Modify: `secret-agents/tests/test_executor.py`

**Interfaces:**
- Produces `PartialLinkCleanupFailed(destination: Path, create_error: BaseException, cleanup_error: Exception)` with `recoverable_path` equal to `destination`.
- `LinkBackend.create_file_link` and `create_directory_link` either return with a verified link or raise with no link remaining; cleanup failure is the only exception and identifies the path.
- `ExecutionError.recoverable_paths` includes a `PartialLinkCleanupFailed.recoverable_path` in addition to rollback-journal failures.

- [ ] **Step 1: Write failing backend tests for post-create verification failure**

In `test_links.py`, inject or monkeypatch verification so the OS link is created and verification then raises `LinkTargetMismatch`. Cover file and directory creation. Assert the original mismatch is raised and `os.path.lexists(destination)` is false.

Add a cleanup-failure case by injecting a remover that raises; assert `PartialLinkCleanupFailed.destination` and both causes are preserved.

- [ ] **Step 2: Write the executor-level failing recovery-path test**

Use a fake backend whose create operation materializes the destination and then raises `PartialLinkCleanupFailed`. Assert `apply_install_plan` raises `ExecutionError` containing the destination once in `recoverable_paths` even though no journal compensation exists for that incomplete call.

- [ ] **Step 3: Run focused tests and observe RED**

Run:

```text
python -m pytest tests/test_links.py tests/test_executor.py -v
```

Expected: a partial destination remains after verification failure and the cleanup error type is missing.

- [ ] **Step 4: Implement one create-and-verify cleanup path per backend**

Wrap the create-plus-verify sequence so any exception after destination creation attempts `remove_link(destination)`. Re-raise the original error after successful cleanup. If cleanup fails, raise `PartialLinkCleanupFailed` from the original create/verify error.

Do not make the executor guess whether a backend mutated before raising; the backend owns the atomic create contract.

- [ ] **Step 5: Include structured backend recovery paths in `ExecutionError`**

When wrapping an ordinary execution exception, seed the recoverable paths with `original.recoverable_path` only when `isinstance(original, PartialLinkCleanupFailed)`, then append unique rollback-journal recovery paths. Do not inspect message text or use an untyped `getattr` convention.

- [ ] **Step 6: Run focused tests and require GREEN**

```text
python -m pytest tests/test_links.py tests/test_executor.py -v
```

- [ ] **Step 7: Commit Task 3**

```text
git add -- src/secret_agents_setup/links.py src/secret_agents_setup/link_errors.py src/secret_agents_setup/executor.py tests/test_links.py tests/test_executor.py docs/superpowers/plans/2026-08-29-installer-domain-and-cli-redesign.md
git diff --cached --check
git commit -m "fix: clean partial link creations"
```

### Task 4: Preserve Cancellation and Name the Failed Operation

**Model recommendation:** Codex `gpt-5.6-sol` with high reasoning; Claude `claude-opus-5` with high effort (`high-risk`). Cancellation, rollback failure, and process semantics need one explicit contract.

**Files:**
- Modify: `secret-agents/src/secret_agents_setup/executor.py`
- Modify: `secret-agents/src/secret_agents_setup/executor_errors.py`
- Modify: `secret-agents/tests/test_executor.py`
- Modify: `secret-agents/tests/test_uninstall.py`
- Modify: `secret-agents/tests/test_cli.py`

**Interfaces:**
- `ExecutionError(operation: Literal["install", "uninstall"], original: Exception, rollback_failures: tuple[RollbackFailure, ...], recoverable_paths: tuple[Path, ...])`.
- Ordinary `Exception` instances are wrapped after rollback.
- `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit` trigger rollback and are then re-raised as the same object. Rollback failure details are attached with `BaseException.add_note` before re-raising.

- [ ] **Step 1: Characterize the corrected operation-aware diagnostics**

Add an install failure assertion containing `install failed` and an uninstall failure assertion containing `uninstall failed`. Assert the original exception remains available as `.original` and `__cause__`.

- [ ] **Step 2: Write failing cancellation tests for install and uninstall**

Parameterize `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit`. Inject each after one successful mutation. Assert:

```python
with pytest.raises(type(cancellation)) as raised:
    apply_install_plan(...)

assert raised.value is cancellation
assert prior_state_is_restored()
```

Add one rollback-failure case and assert the same cancellation object is raised with a note naming every manually recoverable path.

- [ ] **Step 3: Run focused tests and observe RED**

```text
python -m pytest tests/test_executor.py tests/test_uninstall.py tests/test_cli.py -v
```

Expected: cancellation is currently converted to `ExecutionError`, and uninstall diagnostics say `install failed`.

- [ ] **Step 4: Centralize failure finalization without swallowing cancellation**

Create one private helper used by install and uninstall execution. It rolls back once, wraps only `Exception`, and re-raises non-`Exception` cancellation values after attaching rollback failure/recovery details with `add_note`. Pass the literal operation from each public executor entrypoint.

- [ ] **Step 5: Run focused and Batch 1 verification**

Run:

```text
python -m pytest tests/test_path_safety.py tests/test_receipts.py tests/test_planning.py tests/test_links.py tests/test_executor.py tests/test_uninstall.py tests/test_cli.py -v
python -m pytest --tb=short -q
```

Expected: every command exits zero and the full suite passes.

- [ ] **Step 6: Commit Task 4 and stop Batch 1**

```text
git add -- src/secret_agents_setup/executor.py src/secret_agents_setup/executor_errors.py tests/test_executor.py tests/test_uninstall.py tests/test_cli.py docs/superpowers/plans/2026-08-29-installer-domain-and-cli-redesign.md
git diff --cached --check
git commit -m "fix: preserve cancellation through rollback"
git status --short --branch
```

- [ ] **Batch 1 complete**

---
## Batch 2: Domain Vocabulary and Typed Plans

**Batch routing:** `high-risk`. This batch migrates types shared by profiles, planning, receipts, and execution while keeping schema-v1 receipts and CLI output stable.

### Copy/paste handoff

```text
Implement Batch 2 of the Installer Domain and CLI Redesign plan.

Work only in the existing isolated worktree on branch batch-3-installer-domain-cli-redesign. Read the approved spec, Global Constraints, File and Responsibility Map, Batch 2, and the completed Batch 1 interfaces. Verify `git status --short --branch` is clean and the four Batch 1 commits are present.

Model routing: every task uses high-risk — Codex gpt-5.6-sol/high or Claude claude-opus-5/high. Verify availability before dispatch and record any allowed substitution.

Execute Tasks 5–9 in order. Each task must keep the complete test suite green and commit its own checked plan state. Preserve schema-v1 JSON keys/values and current CLI text. Stop after Task 9's domain gate passes. Report five commits, focused/full test results, and any compatibility re-exports still present (expected: none for Projection/Finding/Action types). Do not start Batch 3.
```

### Task 5: Replace Projections with Explicit Mappings

**Model recommendation:** Codex `gpt-5.6-sol` with high reasoning; Claude `claude-opus-5` with high effort (`high-risk`). The mapping union crosses profiles, planning, receipt construction, and tests.

**Files:**
- Modify: `secret-agents/src/secret_agents_setup/models.py`
- Modify: `secret-agents/src/secret_agents_setup/harness_profiles.py`
- Modify: `secret-agents/src/secret_agents_setup/planning.py`
- Modify: `secret-agents/src/secret_agents_setup/executor.py`
- Modify: `secret-agents/tests/test_harness_profiles.py`
- Modify: `secret-agents/tests/test_planning.py`
- Modify: `secret-agents/tests/test_executor.py`

**Interfaces:**
- Produces frozen `InstructionsMapping(harnesses: tuple[Harness, ...], source: Path, destination: Path)`.
- Produces frozen `SkillsMapping(harnesses: tuple[Harness, ...], source: Path, destination: Path)`.
- Produces `InstallMapping = InstructionsMapping | SkillsMapping`.
- Produces `build_install_mappings(root: AgentRoot, home: Path, harnesses: tuple[Harness, ...]) -> tuple[InstallMapping, ...]`.
- Shared `.agents/skills` destinations merge harness ownership deterministically.
- A mapping's concrete type determines file versus directory behavior; no `ProjectionKind` or `is_directory` field remains.

- [ ] **Step 1: Rewrite profile tests against the approved vocabulary and observe type failures**

Replace projection assertions with concrete mapping assertions. Include:

```python
def test_codex_mappings_name_instructions_and_skills(tmp_path: Path) -> None:
    mappings = build_install_mappings(ROOT, tmp_path, (Harness.CODEX,))

    assert mappings == (
        SkillsMapping((Harness.CODEX,), ROOT.path / "skills", tmp_path / ".agents" / "skills"),
        InstructionsMapping((Harness.CODEX,), ROOT.path / "AGENTS.md", tmp_path / ".codex" / "AGENTS.md"),
    )


def test_shared_skills_mapping_merges_codex_and_copilot(tmp_path: Path) -> None:
    mappings = build_install_mappings(ROOT, tmp_path, (Harness.ALL,))
    shared = next(mapping for mapping in mappings if mapping.destination == tmp_path / ".agents" / "skills")

    assert isinstance(shared, SkillsMapping)
    assert shared.harnesses == (Harness.CODEX, Harness.COPILOT)
```

- [ ] **Step 2: Run mapping tests and observe RED**

```text
python -m pytest tests/test_harness_profiles.py -v
```

Expected: imports for `InstructionsMapping`, `SkillsMapping`, and `build_install_mappings` fail.

- [ ] **Step 3: Implement mappings and migrate consumers without compatibility aliases**

Define the mapping dataclasses and union in `harness_profiles.py`, where the profile rules live. Replace `_ProjectionSpec` with concrete private instruction/skills specs or direct mapping factories. Use `isinstance(mapping, SkillsMapping)` where planning or execution must select directory behavior.

Update current planning/executor structures to carry `mapping` instead of `projection` while retaining their old status/action shapes until Tasks 7–8. Remove `Projection`, `ProjectionKind`, and `build_projections`; do not leave aliases that preserve the old vocabulary.

- [ ] **Step 4: Update focused fixtures and assertions mechanically**

Replace test helpers such as `_guidance_projection` and `_skills_projection` with `_instructions_mapping` and `_skills_mapping`. Preserve all path/state/action expectations; this step changes vocabulary, not behavior.

- [ ] **Step 5: Run focused and full tests**

```text
python -m pytest tests/test_harness_profiles.py tests/test_planning.py tests/test_executor.py -v
python -m pytest --tb=short -q
```

Expected: PASS; stdout string assertions remain unchanged.

- [ ] **Step 6: Commit Task 5**

```text
git add -- src/secret_agents_setup/models.py src/secret_agents_setup/harness_profiles.py src/secret_agents_setup/planning.py src/secret_agents_setup/executor.py tests/test_harness_profiles.py tests/test_planning.py tests/test_executor.py docs/superpowers/plans/2026-08-29-installer-domain-and-cli-redesign.md
git diff --cached --check
git commit -m "refactor: model installer mappings explicitly"
```

### Task 6: Move Receipt Ownership into Receipt Models

**Model recommendation:** Codex `gpt-5.6-sol` with high reasoning; Claude `claude-opus-5` with high effort (`high-risk`). Persisted compatibility and uninstall authority make this a high-risk ownership migration.

**Files:**
- Modify: `secret-agents/src/secret_agents_setup/models.py`
- Modify: `secret-agents/src/secret_agents_setup/receipts.py`
- Modify: `secret-agents/src/secret_agents_setup/planning.py`
- Modify: `secret-agents/src/secret_agents_setup/executor.py`
- Modify: `secret-agents/tests/test_receipts.py`
- Modify: `secret-agents/tests/test_executor.py`
- Modify: `secret-agents/tests/test_uninstall.py`
- Modify: `secret-agents/tests/test_cli.py`

**Interfaces:**
- Produces frozen `OwnedLink(mapping: InstallMapping)`.
- Produces frozen `OwnedBackup(original: Path, backup: Path, sha256: str)`.
- Produces frozen `InstallReceipt(schema_version: int, root_identity: str, installed_root: Path, links: tuple[OwnedLink, ...], backups: tuple[OwnedBackup, ...], created_parents: tuple[Path, ...])` in `receipts.py`.
- JSON continues to use `"projections"`, `"kind": "guidance" | "skills"`, and existing field names/order. `"guidance"` deserializes to `InstructionsMapping`; `"skills"` deserializes to `SkillsMapping`.

- [ ] **Step 1: Add schema-compatibility tests before changing receipt types**

Add a literal version-1 document fixture containing one `"guidance"` and one `"skills"` projection. Assert loading produces:

```python
assert receipt.links == (
    OwnedLink(InstructionsMapping((Harness.CODEX,), instructions_source, instructions_destination)),
    OwnedLink(SkillsMapping((Harness.CODEX,), skills_source, skills_destination)),
)
```

Write the result back and assert the JSON still contains `"projections"` and `"kind": "guidance"`, not new serialized names.

- [ ] **Step 2: Run the receipt test and observe RED**

```text
python -m pytest tests/test_receipts.py -v
```

Expected: `OwnedLink`/`OwnedBackup` imports fail and current receipt fields are still named projections.

- [ ] **Step 3: Move receipt-owned types and schema translation into `receipts.py`**

Use explicit serialization functions:

```python
def _kind_for(mapping: InstallMapping) -> str:
    return "skills" if isinstance(mapping, SkillsMapping) else "guidance"


def _mapping_from_document(...) -> InstallMapping:
    # "skills" -> SkillsMapping; "guidance" -> InstructionsMapping
```

The compatibility string `"guidance"` exists only at the serialization boundary and tests. Remove `ReceiptProjection`, `ReceiptBackup`, and `InstallReceipt` from `models.py`.

- [ ] **Step 4: Migrate receipt consumers to `links` and wrapper-owned mappings**

Update install receipt construction, relocation, partial uninstall, shared-harness retention, and CLI fixtures. Use `owned_link.mapping.source`, `.destination`, and `.harnesses`; never infer ownership from a path-status record.

- [ ] **Step 5: Run receipt, executor, uninstall, and CLI tests**

```text
python -m pytest tests/test_receipts.py tests/test_executor.py tests/test_uninstall.py tests/test_cli.py -v
python -m pytest --tb=short -q
```

Expected: PASS and deterministic receipt snapshots remain schema version 1.

- [ ] **Step 6: Commit Task 6**

```text
git add -- src/secret_agents_setup/models.py src/secret_agents_setup/receipts.py src/secret_agents_setup/planning.py src/secret_agents_setup/executor.py tests/test_receipts.py tests/test_executor.py tests/test_uninstall.py tests/test_cli.py docs/superpowers/plans/2026-08-29-installer-domain-and-cli-redesign.md
git diff --cached --check
git commit -m "refactor: make receipt ownership explicit"
```

### Task 7: Replace Install Findings and Actions with Statuses and Typed Changes

**Model recommendation:** Codex `gpt-5.6-sol` with high reasoning; Claude `claude-opus-5` with high effort (`high-risk`). Planning and execution must migrate together without weakening final validation or receipt ownership.

**Files:**
- Modify: `secret-agents/src/secret_agents_setup/models.py`
- Modify: `secret-agents/src/secret_agents_setup/planning.py`
- Modify: `secret-agents/src/secret_agents_setup/executor.py`
- Modify: `secret-agents/src/secret_agents_setup/cli.py`
- Modify: `secret-agents/tests/test_planning.py`
- Modify: `secret-agents/tests/test_executor.py`
- Modify: `secret-agents/tests/test_cli.py`

**Interfaces:**
- `InstallState`: `CURRENT`, `MISSING`, `STALE_LINK`, `BROKEN_LINK`, `COMPATIBLE_SKILLS_DIRECTORY`, `BACKUP_PLANNED`, `CONFLICT`, `SKILL_NAME_COLLISION`.
- Frozen `PathStatus(state: InstallState, mapping: InstallMapping)` with `path` derived from `mapping.destination` and `blocks_install` derived from state.
- Frozen typed changes: `CreateLink(mapping: InstallMapping)`, `ReplaceLink(mapping: InstallMapping)`, `BackupFile(original: Path, backup: Path)`.
- `InstallChange = CreateLink | ReplaceLink | BackupFile`.
- Frozen `InstallPlan(statuses: tuple[PathStatus, ...], changes: tuple[InstallChange, ...])` with `is_blocked` derived from statuses.
- `InstallState.output_name` preserves current row values: `current -> "correct"`, both backup-planned/conflict -> `"unrelated"`, and other existing values unchanged.

- [ ] **Step 1: Rewrite planning expectations as exact typed values**

Replace tuple-of-kind assertions with complete values, for example:

```python
assert plan.statuses == (PathStatus(InstallState.MISSING, mapping),)
assert plan.changes == (CreateLink(mapping),)
assert plan.is_blocked is False
```

For a compatible real skills directory, construct one child `SkillsMapping` per canonical skill and assert each status/change carries that exact child mapping rather than the parent collection mapping.

Add separate conflict tests proving `BACKUP_PLANNED.blocks_install is False`, `CONFLICT.blocks_install is True`, and both retain the existing `unrelated` output label.

- [ ] **Step 2: Run planning tests and observe RED**

```text
python -m pytest tests/test_planning.py -v
```

Expected: new status/change types are absent.

- [ ] **Step 3: Implement install statuses, changes, and all-or-nothing planning**

Place these install-domain values in `planning.py`. Clear `changes` whenever any status blocks installation. Replace all `Finding`, `FindingState`, `PlannedAction`, and `ActionKind` install usage; remove those definitions from `models.py`.

Use child `SkillsMapping` values during compatible-directory expansion so every status and change tells the truth about its source and destination.

- [ ] **Step 4: Migrate install execution with exhaustive union handling**

Use `isinstance` branches for each typed change and finish with `typing.assert_never(change)`. Link execution derives file/directory behavior from `InstructionsMapping` versus `SkillsMapping`. Final validation returns `PathStatus` values. Receipt construction wraps each successfully owned mapping in `OwnedLink` and no longer builds a destination-to-parent-mapping dictionary or needs the per-skill explanatory comment.

- [ ] **Step 5: Preserve current CLI rows during the transitional boundary**

Update the current CLI printer to use `status.state.output_name` and `status.path`. Do not introduce `Console` or `CommandResult` yet.

- [ ] **Step 6: Run focused and full tests**

```text
python -m pytest tests/test_planning.py tests/test_executor.py tests/test_cli.py -v
python -m pytest --tb=short -q
```

- [ ] **Step 7: Commit Task 7**

```text
git add -- src/secret_agents_setup/models.py src/secret_agents_setup/planning.py src/secret_agents_setup/executor.py src/secret_agents_setup/cli.py tests/test_planning.py tests/test_executor.py tests/test_cli.py docs/superpowers/plans/2026-08-29-installer-domain-and-cli-redesign.md
git diff --cached --check
git commit -m "refactor: type install plans by intent"
```

### Task 8: Replace Uninstall Findings and Actions with Removal Statuses and Changes

**Model recommendation:** Codex `gpt-5.6-sol` with high reasoning; Claude `claude-opus-5` with high effort (`high-risk`). Receipt-owned removal, shared harness retention, and receipt-last ordering must remain exact.

**Files:**
- Modify: `secret-agents/src/secret_agents_setup/models.py`
- Modify: `secret-agents/src/secret_agents_setup/planning.py`
- Modify: `secret-agents/src/secret_agents_setup/executor.py`
- Modify: `secret-agents/src/secret_agents_setup/cli.py`
- Modify: `secret-agents/tests/test_uninstall.py`
- Modify: `secret-agents/tests/test_executor.py`
- Modify: `secret-agents/tests/test_cli.py`

**Interfaces:**
- `RemovalState`: `NOT_INSTALLED`, `OWNED`, `MISSING_OWNED_LINK`, `SHARED_RETAINED`, `FOREIGN_CONTENT`, `BACKUP_MISSING`, `BACKUP_MODIFIED`, `PARENT_PRESERVED`.
- Frozen `RemovalStatus(state: RemovalState, path: Path)` with `blocks_removal` derived from state.
- Frozen changes: `RemoveLink(link: OwnedLink)`, `RestoreFile(backup: OwnedBackup)`, `RemoveDirectory(path: Path)`, `WriteReceipt(path: Path, receipt: InstallReceipt)`, `DeleteReceipt(path: Path)`.
- `RemovalChange` is the union of those five types.
- Frozen `UninstallPlan(statuses: tuple[RemovalStatus, ...], changes: tuple[RemovalChange, ...])` with `is_blocked`; receipt changes own their receipt path, so `apply_uninstall_plan` no longer accepts a separate `receipt_file`.

- [ ] **Step 1: Rewrite uninstall plan assertions as complete typed values**

Cover no receipt, selected harness filtering, shared retention, missing owned links, foreign content, backup restore, parent preservation, partial receipt write, and full receipt delete. Assert receipt mutation is always the last typed change and an externally supplied second receipt path no longer exists in the executor interface.

- [ ] **Step 2: Run uninstall tests and observe RED**

```text
python -m pytest tests/test_uninstall.py -v
```

Expected: removal status/change types are missing and `apply_uninstall_plan` still requires a separate receipt path.

- [ ] **Step 3: Implement derived removal states and typed changes**

Place removal values in `planning.py`. Derive blocking only from `FOREIGN_CONTENT`, `BACKUP_MISSING`, and `BACKUP_MODIFIED`. Preserve deterministic order: remove links, restore files, remove deepest empty directories, then write/delete receipt.

Remove `UninstallFinding`, `UninstallFindingState`, `UninstallAction`, and `UninstallActionKind` from `models.py`.

- [ ] **Step 4: Migrate uninstall execution and rollback**

Apply each typed change with `isinstance` plus `assert_never`. Read the receipt path from `WriteReceipt`/`DeleteReceipt`, eliminating the competing executor parameter. Use the concrete owned mapping to recreate file versus directory links during rollback.

- [ ] **Step 5: Preserve current uninstall output labels**

Give `RemovalState` the existing serialized/output values and update the transitional CLI printer to consume `plan.statuses`.

- [ ] **Step 6: Run focused and full tests**

```text
python -m pytest tests/test_uninstall.py tests/test_executor.py tests/test_cli.py -v
python -m pytest --tb=short -q
```

- [ ] **Step 7: Commit Task 8**

```text
git add -- src/secret_agents_setup/models.py src/secret_agents_setup/planning.py src/secret_agents_setup/executor.py src/secret_agents_setup/cli.py tests/test_uninstall.py tests/test_executor.py tests/test_cli.py docs/superpowers/plans/2026-08-29-installer-domain-and-cli-redesign.md
git diff --cached --check
git commit -m "refactor: type uninstall plans by ownership"
```

### Task 9: Give Install and Uninstall Explicit Execution Results

**Model recommendation:** Codex `gpt-5.6-sol` with high reasoning; Claude `claude-opus-5` with high effort (`high-risk`). Result semantics feed the later command boundary and must eliminate implicit not-installed decoding.

**Files:**
- Modify: `secret-agents/src/secret_agents_setup/models.py`
- Modify: `secret-agents/src/secret_agents_setup/executor.py`
- Modify: `secret-agents/src/secret_agents_setup/cli.py`
- Modify: `secret-agents/tests/test_executor.py`
- Modify: `secret-agents/tests/test_uninstall.py`
- Modify: `secret-agents/tests/test_cli.py`

**Interfaces:**
- `AppliedOperation` retains existing applied row values such as `created-link`, `wrote-receipt`, and `restored-backup`.
- Frozen `AppliedChange(operation: AppliedOperation, path: Path)`.
- `InstallResultState`: `UNCHANGED`, `INSTALLED`, `UPDATED`.
- `UninstallResultState`: `NOT_INSTALLED`, `PARTIALLY_UNINSTALLED`, `UNINSTALLED`.
- Frozen `InstallResult(state: InstallResultState, changes: tuple[AppliedChange, ...], receipt: InstallReceipt | None)`.
- Frozen `UninstallResult(state: UninstallResultState, changes: tuple[AppliedChange, ...], receipt: InstallReceipt | None)`.

- [ ] **Step 1: Add failing explicit-result tests**

Replace event/report helper assertions with complete result states. At minimum assert:

```python
assert unowned_noop.state is InstallResultState.UNCHANGED
assert no_receipt_uninstall.state is UninstallResultState.NOT_INSTALLED
assert partial.state is UninstallResultState.PARTIALLY_UNINSTALLED
assert complete.state is UninstallResultState.UNINSTALLED
```

Prove CLI no longer needs to infer not-installed from `receipt is None and not events` after the executor migration.

- [ ] **Step 2: Run result tests and observe RED**

```text
python -m pytest tests/test_executor.py tests/test_uninstall.py tests/test_cli.py -v
```

Expected: `ExecutionReport`, `ExecutionEvent`, and implicit no-op interpretation remain.

- [ ] **Step 3: Implement result types beside executor behavior**

Move applied/result values into `executor.py`. Return the explicit state at every public executor exit. Remove `ExecutionEventKind`, `ExecutionEvent`, and `ExecutionReport` from `models.py`.

- [ ] **Step 4: Migrate the transitional CLI to explicit states**

Print applied rows from `result.changes`. Select `not-installed` only from `UninstallResultState.NOT_INSTALLED`; remove `_is_noop`.

- [ ] **Step 5: Prove the old domain vocabulary is gone**

Run:

```text
rg -n "Projection|Finding|PlannedAction|ActionKind|ExecutionEvent|ExecutionReport|UninstallAction" src tests
```

Expected: no active code/test matches. Compatibility JSON fixtures may contain lowercase `projections` and `guidance` only.

- [ ] **Step 6: Run the Batch 2 domain gate**

```text
python -m mypy
python -m ruff check src tests scripts skills/update-model-routing/scripts
python -m ruff format --check src tests scripts skills/update-model-routing/scripts
python -m pytest --tb=short -q
python -m compileall -q src tests scripts skills/update-model-routing/scripts
git diff --check
```

Expected: every command exits zero.

- [ ] **Step 7: Commit Task 9 and stop Batch 2**

```text
git add -- src/secret_agents_setup/models.py src/secret_agents_setup/executor.py src/secret_agents_setup/cli.py tests/test_executor.py tests/test_uninstall.py tests/test_cli.py docs/superpowers/plans/2026-08-29-installer-domain-and-cli-redesign.md
git diff --cached --check
git commit -m "refactor: return explicit execution results"
git status --short --branch
```

- [ ] **Batch 2 complete**

---

## Batch 3: Command and Presentation Boundaries

**Batch routing:** `high-risk` for command orchestration, `balanced` for presentation, and `routine` for the architecture guard. This batch changes dependency ownership and every handled CLI outcome while preserving the public contract.

### Copy/paste handoff

```text
Implement Batch 3 of the Installer Domain and CLI Redesign plan.

Repository root: C:\git\handbag-of-holding
Working branch: batch-3-installer-domain-cli-redesign
Plan: secret-agents/docs/superpowers/plans/2026-08-29-installer-domain-and-cli-redesign.md
Spec: secret-agents/docs/superpowers/specs/2026-08-29-installer-domain-and-cli-design.md

Continue in the clean isolated worktree created by Batch 1. Verify `git branch --show-current` is exactly `batch-3-installer-domain-cli-redesign`; do not create another branch and do not work in the dirty source worktree. Require Tasks 1–9 and Batches 1–2 to be checked and their commits to be present before editing.

Model routing:
- Task 10: high-risk — Codex gpt-5.6-sol/high or Claude claude-opus-5/high.
- Task 11: balanced — Codex gpt-5.6-terra/high or Claude claude-sonnet-5/high.
- Task 12: routine — Codex gpt-5.6-terra/medium or Claude claude-sonnet-5/medium.
Verify availability before dispatch and record any allowed substitution.

Read the approved spec sections "Ownership and module boundaries", "CLI result and presentation boundary", "Error contract", and "Command-specific setup". Then read commands.py, console.py, and their tests as each is created; do not reintroduce a session/context bag.

Execute Tasks 10–12 with strict RED/GREEN. Preserve argparse help/error behavior and every successfully parsed command's line-oriented stdout, stderr, and numeric exit code. Update plan checkboxes in each task commit. Stop after the architecture guard's planted violation and the full Batch 3 gate pass. Report three commits, exact test/gate results, and any model substitutions. Do not start Batch 4.
```

### Task 10: Make Command Dependencies and Outcomes Explicit

**Model recommendation:** Codex `gpt-5.6-sol` with high reasoning; Claude `claude-opus-5` with high effort (`high-risk`). The change separates three command dependency graphs while preserving transaction and error semantics.

**Files:**
- Create: `secret-agents/src/secret_agents_setup/commands.py`
- Modify: `secret-agents/src/secret_agents_setup/cli.py`
- Create: `secret-agents/tests/test_commands.py`
- Modify: `secret-agents/tests/test_cli.py`

**Interfaces:**
- `CommandStatus(StrEnum)`: `OK`, `NOT_INSTALLED`, `BLOCKED`, `FAILED`, `INVALID_INPUT`.
- `DiagnosticReason(StrEnum)`: `INVALID_INPUT`, `REMEDIATION_REQUIRED`, `INSTALL_BLOCKED`, `UNINSTALL_BLOCKED`, `CAPABILITY_UNAVAILABLE`, `BACKUP_DESTINATION_OCCUPIED`, `EXECUTION_FAILED`.
- Frozen `CommandDiagnostic(reason: DiagnosticReason, cause: Exception | None = None, paths: tuple[Path, ...] = ())`. The optional cause remains the concrete semantic error from the owning domain; commands do not flatten it to a formatted string. `paths` carries recovery/occupied-path context without parsing the cause's message.
- Frozen `CommandResult(status: CommandStatus, root: AgentRoot | None, harness_selector: str | None, statuses: tuple[PathStatus | RemovalStatus, ...], changes: tuple[AppliedChange, ...], diagnostic: CommandDiagnostic | None, capability_unverified: bool = False)`.
- `check(root: AgentRoot, harness_selector: str, harnesses: tuple[Harness, ...], home: Path, catalog: tuple[SkillDescriptor, ...], now: datetime, os_name: str) -> CommandResult`.
- `install(root: AgentRoot, harness_selector: str, harnesses: tuple[Harness, ...], home: Path, catalog: tuple[SkillDescriptor, ...], now: datetime, os_name: str, backend: LinkBackend, *, dry_run: bool, backup_conflicts: bool) -> CommandResult`.
- `uninstall(root: AgentRoot, harness_selector: str, harnesses: tuple[Harness, ...], home: Path, backend: LinkBackend) -> CommandResult`.
- `cli.py` resolves the root for every command, loads the catalog only for `check` and `install`, constructs the backend only for `install` and `uninstall`, and passes the explicit values above.

- [ ] **Step 1: Add failing command-value tests**

Create `tests/test_commands.py`. Call each command function directly and assert complete `CommandResult` values for:

- current check -> `OK`;
- missing/stale check -> `BLOCKED` with path statuses and remediation diagnostic;
- install dry-run applicable/blocked -> `OK`/`BLOCKED`, no changes, and no backend probe;
- install unchanged/installed/updated -> `OK` with the executor's explicit changes;
- no-receipt uninstall -> `NOT_INSTALLED`;
- partial/full uninstall -> `OK` with removal statuses and applied changes;
- invalid receipt or unsupported link capability -> `BLOCKED` with the original semantic exception in `diagnostic.cause`;
- `ExecutionError` -> `FAILED`, preserving the exception in `diagnostic.cause` and its recovery paths in `diagnostic.paths`;
- programmer errors and cancellation -> the identical exception escapes.

Use `capsys` to prove every direct command call leaves both streams empty.

- [ ] **Step 2: Add a failing uninstall-dependency regression**

In `tests/test_cli.py`, create a valid receipt, corrupt a current canonical `SKILL.md`, then invoke uninstall with an injected home/backend. Assert uninstall completes from receipt-owned state and never calls `load_skill_catalog` or `build_install_mappings`. Add the no-receipt variant and require `NOT_INSTALLED` semantics even when the catalog is malformed.

- [ ] **Step 3: Run the focused tests and observe RED**

```text
python -m pytest tests/test_commands.py tests/test_cli.py -v
```

Expected: `commands.py` and command result types do not exist; current `_open_session` also loads the malformed catalog before uninstall.

- [ ] **Step 4: Implement command-specific orchestration**

Move check/install/uninstall orchestration into the three explicit functions. Commands may construct mappings and plans, load/write receipts, invoke executors, and classify known semantic outcomes. They must not parse exception text, print, import `Console`/`ExitCode`, catch `BaseException`, or translate programmer errors/cancellation.

Keep root resolution and catalog loading in `cli.py` because those are dependency construction. Dispatch on the parsed command before catalog loading. Delete `_Session`, `_open_session`, `_run_check`, `_run_install`, `_run_uninstall`, and `_apply_install` after their callers migrate; do not retain compatibility aliases for private names.

- [ ] **Step 5: Run focused tests and observe GREEN**

```text
python -m pytest tests/test_commands.py tests/test_cli.py -v
```

- [ ] **Step 6: Commit Task 10**

```text
git add -- src/secret_agents_setup/commands.py src/secret_agents_setup/cli.py tests/test_commands.py tests/test_cli.py docs/superpowers/plans/2026-08-29-installer-domain-and-cli-redesign.md
git diff --cached --check
git commit -m "refactor: separate installer command workflows"
```

### Task 11: Give Console Sole Ownership of Presentation

**Model recommendation:** Codex `gpt-5.6-terra` with high reasoning; Claude `claude-sonnet-5` with high effort (`balanced`). The implementation is localized, but the output and failure matrix is a public compatibility boundary.

**Files:**
- Create: `secret-agents/src/secret_agents_setup/console.py`
- Modify: `secret-agents/src/secret_agents_setup/cli.py`
- Modify: `secret-agents/src/secret_agents_setup/__main__.py`
- Create: `secret-agents/tests/test_console.py`
- Modify: `secret-agents/tests/test_cli.py`

**Interfaces:**
- `ExitCode(IntEnum)`: `SUCCESS = 0`, `INVALID_INPUT = 2`, `BLOCKED = 3`, `EXECUTION_FAILED = 4`.
- `Console(stdout: TextIO, stderr: TextIO)` with `present(result: CommandResult) -> int`.
- `Console` renders, in order: optional `root`, optional `harness`, status rows, optional capability note, applied-change rows, final result row, then any diagnostic on stderr.
- `main(...) -> int` retains every existing injectable parameter and may add `console: Console | None = None`; when absent, construct `Console(sys.stdout, sys.stderr)` at call time so pytest capture and normal process streams work.
- Argparse alone retains its native help/usage output and `SystemExit` conversion. Every successfully parsed command returns through exactly one `console.present(result)` call.

- [ ] **Step 1: Freeze the presentation matrix in failing tests**

Create table-driven `tests/test_console.py` cases for all five command statuses. Assert exact stdout, exact stderr, and exact integer return values, including:

```text
OK / NOT_INSTALLED -> 0
INVALID_INPUT -> 2
BLOCKED -> 3
FAILED -> 4
```

Cover install and removal status rows, applied-change rows, `note capability-unverified-until-install`, silent blocked dry-run, actionable blocked diagnostics, and execution recovery paths. Preserve the existing tokens `finding`, `did`, `result ok`, `result not-installed`, `result blocked`, `result failed`, and `error:` unless the approved spec explicitly corrected their content.

- [ ] **Step 2: Run console tests and observe RED**

```text
python -m pytest tests/test_console.py tests/test_cli.py -v
```

Expected: `console.py` does not exist and `cli.py` still prints/maps statuses itself.

- [ ] **Step 3: Implement Console and reduce CLI to its boundary role**

Move `ExitCode`, stable output templates, row rendering, stream selection, and status-to-exit mapping into `console.py`. Move no planning, receipt, or execution policy there. Reduce `main` to parse, build only the selected command's dependencies, obtain one `CommandResult`, and call `console.present` once.

Delete `_print`, `_err`, `_print_findings`, `_print_events`, `_ok`, `_not_installed`, `_blocked`, `_silent_blocked`, `_failed`, `_is_noop`, and `_note_windows_capability`. Update tests to import `ExitCode` from `console.py`; do not re-export it from `cli.py` merely to preserve a test-only import.

- [ ] **Step 4: Verify parser and presentation behavior**

```text
python -m pytest tests/test_console.py tests/test_commands.py tests/test_cli.py -v
python scripts/harness_setup.py --help
```

Expected: tests pass and help lists `install`, `check`, and `uninstall`. The help command must not touch the real home.

- [ ] **Step 5: Commit Task 11**

```text
git add -- src/secret_agents_setup/console.py src/secret_agents_setup/cli.py src/secret_agents_setup/__main__.py tests/test_console.py tests/test_cli.py docs/superpowers/plans/2026-08-29-installer-domain-and-cli-redesign.md
git diff --cached --check
git commit -m "refactor: centralize CLI presentation"
```

### Task 12: Enforce the Command/Presentation Boundary

**Model recommendation:** Codex `gpt-5.6-terra` with medium reasoning; Claude `claude-sonnet-5` with medium effort (`routine`). The rule and AST mechanism are precise and mechanically testable.

**Files:**
- Create: `secret-agents/tests/test_cli_architecture.py`

**Interfaces:**
- A small AST scanner returns violations for a source string and module name.
- The enforced rule: command modules do not call built-in `print`, import `Console` or `ExitCode`, define an `IntEnum` exit-code mapping, or write directly to `sys.stdout`/`sys.stderr`.
- The real-tree guard scans `src/secret_agents_setup/commands.py` plus any future `*_commands.py` and fails if that set is empty.

- [ ] **Step 1: Write the scanner's planted-violation tests**

Feed synthetic source containing all forbidden forms into the scanner and assert the reported file, line, and reason for each. Add one clean synthetic command module and prove it passes. Do not use regex for imports or calls.

- [ ] **Step 2: Add the real-tree guard and fail-on-empty assertion**

Parse every selected module with `ast.parse`. Resolve both absolute and relative imports. Assert at least `commands.py` is scanned, then assert the aggregate violation list is empty. Temporarily inject a synthetic offender only through the scanner test; never edit production code merely to demonstrate RED.

- [ ] **Step 3: Run the guard and focused presentation suite**

```text
python -m pytest tests/test_cli_architecture.py tests/test_console.py tests/test_commands.py tests/test_cli.py -v
```

Expected: planted violations are detected, real modules pass, and presentation behavior remains green.

- [ ] **Step 4: Run the Batch 3 gate**

```text
python -m mypy
python -m ruff check src tests scripts skills/update-model-routing/scripts
python -m ruff format --check src tests scripts skills/update-model-routing/scripts
python -m pytest --tb=short -q
python -m compileall -q src tests scripts skills/update-model-routing/scripts
git diff --check
```

Expected: every command exits zero.

- [ ] **Step 5: Commit Task 12 and stop Batch 3**

```text
git add -- tests/test_cli_architecture.py docs/superpowers/plans/2026-08-29-installer-domain-and-cli-redesign.md
git diff --cached --check
git commit -m "test: guard the CLI presentation boundary"
git status --short --branch
```

- [ ] **Batch 3 complete**

---

## Batch 4: Acceptance, Review, and Pull Request

**Batch routing:** `high-risk` for the final behavioral audit and `routine` for mechanical delivery. This batch closes compatibility evidence before publishing the replacement PR.

### Copy/paste handoff

```text
Complete Batch 4 and deliver the Installer Domain and CLI Redesign pull request.

Repository root: C:\git\handbag-of-holding
Working branch: batch-3-installer-domain-cli-redesign
Base branch: main
Plan: secret-agents/docs/superpowers/plans/2026-08-29-installer-domain-and-cli-redesign.md
Spec: secret-agents/docs/superpowers/specs/2026-08-29-installer-domain-and-cli-design.md

Continue in the clean isolated worktree. Verify `git branch --show-current` is exactly `batch-3-installer-domain-cli-redesign`; if it is not, stop without switching a dirty tree. Require Batches 1–3 and Tasks 1–12 to be checked and committed.

Model routing:
- Task 13: high-risk — Codex gpt-5.6-sol/high or Claude claude-opus-5/high.
- Task 14: routine — Codex gpt-5.6-terra/medium or Claude claude-sonnet-5/medium.
Verify availability before dispatch and record any allowed substitution.

Task 13 is an adversarial review, not a feature-expansion pass. Close only violations of the approved spec, verified safety defects, compatibility contract, or architecture guard. Do not implement the older cross-platform plan's Batch 4 documentation/CI work in this PR.

After Task 13 and the complete Task 14 quality gate pass, create any final plan-only commit, push `batch-3-installer-domain-cli-redesign`, and submit a GitHub pull request targeting `main`. The PR must state that it supersedes the earlier Batch 3 PR. Verify the remote PR's head/base/state and return its URL. A locally complete branch without an actual PR URL is not a completed handoff.
```

### Task 13: Run the Adversarial Acceptance Review

**Model recommendation:** Codex `gpt-5.6-sol` with high reasoning; Claude `claude-opus-5` with high effort (`high-risk`). This review crosses containment, transactions, persisted compatibility, orchestration, and presentation.

**Files:**
- Modify as failures require: `secret-agents/tests/test_integration.py`
- Modify as failures require: focused modules and tests named by the failing acceptance case
- Modify: `secret-agents/docs/superpowers/plans/2026-08-29-installer-domain-and-cli-redesign.md`

**Acceptance matrix:**

| Contract | Required evidence |
|---|---|
| Managed-home safety | Lexical `..` and linked-parent escape both block uninstall with no mutation |
| Backup ownership | Occupied deterministic backup is byte-preserved and original content is unmoved |
| Atomic backend | Post-creation verification failure removes the partial link; cleanup failure names the recoverable path |
| Cancellation | Rollback runs and the original `KeyboardInterrupt`, `SystemExit`, or `GeneratorExit` escapes |
| Receipt compatibility | Version-1 fixture round-trips deterministically with serialized `"projections"` and `"guidance"` |
| Command setup | Malformed catalog blocks check/install but cannot block receipt-based uninstall |
| Presentation | Parsed commands use `CommandResult -> Console.present`; output/streams/exit codes match the frozen matrix |
| Lifecycle | Temporary-home dry-run/install/check/idempotent install/uninstall preserves canonical and third-party content |

- [ ] **Step 1: Inventory acceptance coverage before editing**

Map every row above to an existing named test. Add a missing test only when no existing test proves the complete contract. Do not duplicate a focused test in `test_integration.py`; integration owns only cross-module lifecycle evidence.

- [ ] **Step 2: Run the adversarial suite**

```text
python -m pytest tests/test_path_safety.py tests/test_receipts.py tests/test_links.py tests/test_executor.py tests/test_uninstall.py tests/test_commands.py tests/test_console.py tests/test_cli.py tests/test_cli_architecture.py tests/test_integration.py -v
```

Expected: every acceptance row is exercised and every test passes. If a failure reveals a production defect, add/confirm the focused RED test, make the smallest compliant fix, and rerun the named focused module before this suite.

- [ ] **Step 3: Prove superseded vocabulary and structure are absent**

```text
rg -n "GuidanceMapping|Projection|Finding|PlannedAction|ActionKind|ExecutionEvent|ExecutionReport|UninstallAction|_Session|_open_session|_print_findings|_print_events" src tests
rg -n "print\(|sys\.stdout|sys\.stderr|ExitCode" src/secret_agents_setup/commands.py
```

Expected: both commands return no matches. Lowercase `projections` and `guidance` remain only in version-1 serialization code/fixtures and are intentionally excluded from this capitalized scan.

- [ ] **Step 4: Review the final diff against the approved spec**

Run `git diff batch-3-rollback-execution-and-cli...HEAD -- src tests`. Confirm each production file has one responsibility from the file map, no comment explains a name that should be made direct, no command loads another command's dependencies, and no compatibility shim keeps rejected active vocabulary alive. Make any necessary fix through a focused RED/GREEN cycle.

- [ ] **Step 5: Commit Task 13 evidence or fixes**

If Task 13 changed tests or production code, stage only those files plus the plan, run `git diff --cached --check`, and commit with a message naming the closed contract. If no code/test change was required, commit the checked Task 13 plan steps:

```text
git add -- docs/superpowers/plans/2026-08-29-installer-domain-and-cli-redesign.md
git diff --cached --check
git commit -m "test: verify installer redesign acceptance"
```

### Task 14: Verify, Push, and Submit the Pull Request

**Model recommendation:** Codex `gpt-5.6-terra` with medium reasoning; Claude `claude-sonnet-5` with medium effort (`routine`). All design decisions are closed; this task performs deterministic verification and delivery.

**Files:**
- Modify: `secret-agents/docs/superpowers/plans/2026-08-29-installer-domain-and-cli-redesign.md`

- [ ] **Step 1: Verify branch identity and scope**

From `secret-agents`:

```text
git branch --show-current
git status --short --branch
git log --oneline batch-3-rollback-execution-and-cli..HEAD
git diff --check batch-3-rollback-execution-and-cli...HEAD
```

Require branch `batch-3-installer-domain-cli-redesign`. The worktree must contain no uncommitted implementation changes and the commit list must contain the completed task commits only.

- [ ] **Step 2: Run the complete quality gate from fresh output**

```text
python -m mypy
python skills/update-model-routing/scripts/check_staleness.py --reference model-routing.json
python -m ruff check src tests scripts skills/update-model-routing/scripts
python -m ruff format --check src tests scripts skills/update-model-routing/scripts
python -m pytest --tb=short -q
python -m compileall -q src tests scripts skills/update-model-routing/scripts
git diff --check
```

Expected: every command exits zero. Do not reuse Task 13 output and do not claim completion from a partial gate.

- [ ] **Step 3: Run read-only process smoke tests**

```text
python scripts/harness_setup.py --help
python scripts/harness_setup.py check --harness all --agent-root .
```

Expected: help succeeds; check reports the real home read-only and may exit `0` or `3` according to its current state. Never run install or uninstall against the developer's real home. Use the pytest temporary-home lifecycle as mutation evidence.

- [ ] **Step 4: Commit the pre-delivery plan evidence**

Check Task 14 Steps 1–3 and every completion item whose evidence now exists. Do not check Task 14, Batch 4, push, or PR items yet. Then commit only the plan:

```text
git add -- docs/superpowers/plans/2026-08-29-installer-domain-and-cli-redesign.md
git diff --cached --check
git commit -m "docs: record installer redesign verification"
git status --short --branch
```

Require a clean worktree before pushing.

- [ ] **Step 5: Push the implementation branch**

```text
git push -u origin batch-3-installer-domain-cli-redesign
```

Do not force-push. If authentication, remote policy, or a non-fast-forward rejection prevents the push, stop and report the exact blocker without claiming delivery.

- [ ] **Step 6: Submit the replacement pull request**

From the repository root, create or update the PR with GitHub CLI:

```text
$prBody = @'
## Summary
- replace projection/finding/action vocabulary with mappings, exact statuses, and typed changes
- correct managed-home, backup no-clobber, partial-link cleanup, cancellation, and uninstall setup defects
- separate command orchestration from one Console-owned presentation and exit-code boundary

## Verification
- mypy strict
- model-routing freshness
- Ruff check and format check
- complete pytest suite
- compileall
- git diff --check

This supersedes the earlier Batch 3 rollback-execution-and-CLI pull request.
'@
$existingPr = gh pr list --base main --head batch-3-installer-domain-cli-redesign --state open --json url --jq '.[0].url'
if ($existingPr) {
    gh pr edit $existingPr --title "Refactor harness installer domain and CLI" --body $prBody
} else {
    gh pr create --base main --head batch-3-installer-domain-cli-redesign --title "Refactor harness installer domain and CLI" --body $prBody
}
```

Do not create a duplicate or target the prior feature branch.

- [ ] **Step 7: Verify and report the submitted PR**

```text
gh pr view batch-3-installer-domain-cli-redesign --json url,state,baseRefName,headRefName
```

Require `state` to be `OPEN`, `baseRefName` to be `main`, and `headRefName` to be `batch-3-installer-domain-cli-redesign`. Record the returned URL in the handoff. If `gh` is unavailable or unauthenticated, the task remains incomplete; report that exact external blocker.

- [ ] **Step 8: Close the plan and push its final state**

After Step 7 succeeds, check Steps 5–8, Task 14, Batch 4, and every now-proven completion item. Commit and push the closure:

```text
git add -- docs/superpowers/plans/2026-08-29-installer-domain-and-cli-redesign.md
git diff --cached --check
git commit -m "docs: complete installer redesign plan"
git push
git status --short --branch
gh pr view batch-3-installer-domain-cli-redesign --json url,state,baseRefName,headRefName
```

Require a clean worktree, an up-to-date remote branch, and the same verified open PR URL before reporting completion.

- [ ] **Task 14 complete**

- [ ] **Batch 4 complete**

---

## Completion Checklist

- [ ] All four batches and all fourteen tasks are checked and committed on `batch-3-installer-domain-cli-redesign`.
- [ ] The five verified defects have focused regression coverage and pass: managed-home escape, backup overwrite race, partial-link cleanup, uninstall catalog coupling, and cancellation/operation diagnostics.
- [ ] Active code uses `InstructionsMapping`, `SkillsMapping`, exact install/removal statuses, typed changes, owned receipt records, and explicit execution/command results.
- [ ] Receipt schema version 1 still reads and writes deterministic `"projections"`/`"guidance"` JSON.
- [ ] `_Session` and distributed CLI printing/exit mapping are absent; the planted architecture violation proves the guard fails correctly.
- [ ] The complete mypy, routing-freshness, Ruff, pytest, compileall, and diff checks pass from fresh output.
- [ ] The implementation branch is pushed without force and the open PR targets `main`.
- [ ] The final handoff includes the verified GitHub pull-request URL, commit list, exact gate results, and any model substitutions.
