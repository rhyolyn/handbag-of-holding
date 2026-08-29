"""Journaled install execution with rollback and post-install validation."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

from .executor_errors import ExecutionError as ExecutionError
from .executor_errors import RollbackFailure
from .links import LinkBackend
from .models import (
    ActionKind,
    AgentRoot,
    ExecutionEvent,
    ExecutionEventKind,
    ExecutionReport,
    Finding,
    FindingState,
    Harness,
    InstallPlan,
    InstallReceipt,
    PlannedAction,
    Projection,
    ReceiptBackup,
    ReceiptProjection,
    UninstallAction,
    UninstallActionKind,
    UninstallPlan,
)
from .receipts import RECEIPT_SCHEMA_VERSION, file_sha256, write_receipt_atomic

_HARNESS_ORDER = (Harness.CODEX, Harness.CLAUDE, Harness.COPILOT)
_LINK_ACTIONS = (ActionKind.CREATE_LINK, ActionKind.REPLACE_LINK)


def apply_install_plan(
    plan: InstallPlan,
    root: AgentRoot,
    probe_root: Path,
    backend: LinkBackend,
    receipt_file: Path,
    existing_receipt: InstallReceipt | None,
) -> ExecutionReport:
    """Execute an applicable plan transactionally, rolling back every mutation on failure."""
    if not plan.can_apply:
        raise ValueError("cannot apply a blocked install plan")
    if not plan.actions and existing_receipt is None:
        return ExecutionReport(events=(), receipt=None, receipt_written=False)

    projection_by_destination = {finding.path: finding.projection for finding in plan.findings}
    run = _InstallRun(backend)

    if _has_file_link_action(plan):
        backend.probe_file_link_capability(probe_root)
        run.events.append(ExecutionEvent(ExecutionEventKind.PROBED_CAPABILITY, probe_root))

    try:
        for action in plan.actions:
            run.execute(action)
        validation = validate_installed_plan(plan, backend)
        if any(finding.state is not FindingState.CORRECT for finding in validation):
            raise _FinalValidationFailed(validation)

        receipt = _build_receipt(plan, root, existing_receipt, run, projection_by_destination)
        if existing_receipt is None or receipt != existing_receipt:
            run.write_receipt(receipt, receipt_file)
            return ExecutionReport(tuple(run.events), receipt, True)
        return ExecutionReport(tuple(run.events), existing_receipt, False)
    except BaseException as original:
        failures, recoverable = run.rollback()
        raise ExecutionError(original, failures, recoverable) from original


def validate_installed_plan(plan: InstallPlan, backend: LinkBackend) -> tuple[Finding, ...]:
    """Re-check every mutated link and report CORRECT or a mismatch state."""
    projection_by_destination = {finding.path: finding.projection for finding in plan.findings}
    findings: list[Finding] = []
    for action in plan.actions:
        if action.kind not in _LINK_ACTIONS:
            continue
        projection = projection_by_destination[action.destination]
        resolved = backend.resolved_target(action.destination)
        state = FindingState.CORRECT if resolved == action.source.resolve() else FindingState.STALE_LINK
        findings.append(Finding(state, action.destination, projection))
    return tuple(findings)


def apply_uninstall_plan(plan: UninstallPlan, backend: LinkBackend, receipt_file: Path) -> ExecutionReport:
    """Execute an applicable uninstall plan transactionally, rolling back on failure."""
    if not plan.can_apply:
        raise ValueError("cannot apply a blocked uninstall plan")
    if not plan.actions:
        return ExecutionReport(events=(), receipt=plan.next_receipt, receipt_written=False)

    run = _UninstallRun(backend)
    try:
        for action in plan.actions:
            run.execute(action, plan.next_receipt, receipt_file)
        receipt_written = any(action.kind is UninstallActionKind.REPLACE_RECEIPT for action in plan.actions)
        return ExecutionReport(tuple(run.events), plan.next_receipt, receipt_written)
    except BaseException as original:
        failures, recoverable = run.rollback()
        raise ExecutionError(original, failures, recoverable) from original


class _FinalValidationFailed(Exception):
    def __init__(self, findings: tuple[Finding, ...]) -> None:
        self.findings = findings
        super().__init__("post-install validation failed")


class _CompensationKind(StrEnum):
    REMOVE_LINK = "remove-link"
    REMOVE_PARENT = "remove-parent"
    MAKE_PARENT = "make-parent"
    MOVE_PATH = "move-path"
    RECREATE_LINK = "recreate-link"
    RESTORE_RECEIPT = "restore-receipt"
    DELETE_RECEIPT = "delete-receipt"


@dataclass(frozen=True)
class _Compensation:
    kind: _CompensationKind
    target: Path
    other: Path | None = None
    is_directory: bool = False
    payload: bytes | None = None


class _Transaction:
    """Shared event log and typed compensation journal with best-effort rollback."""

    def __init__(self, backend: LinkBackend) -> None:
        self.backend = backend
        self.events: list[ExecutionEvent] = []
        self.journal: list[_Compensation] = []

    def rollback(self) -> tuple[tuple[RollbackFailure, ...], tuple[Path, ...]]:
        failures: list[RollbackFailure] = []
        recoverable: list[Path] = []
        for compensation in reversed(self.journal):
            # Rollback is best-effort: attempt every compensation and surface all
            # failures through recoverable_paths rather than aborting on the first.
            try:
                self._compensate(compensation)
            except Exception as exc:
                failures.append(RollbackFailure(compensation.kind.value, compensation.target, str(exc)))
                recoverable.append(compensation.target)
        return tuple(failures), tuple(recoverable)

    def _compensate(self, compensation: _Compensation) -> None:
        kind = compensation.kind
        if kind is _CompensationKind.REMOVE_LINK:
            self.backend.remove_link(compensation.target)
        elif kind is _CompensationKind.REMOVE_PARENT:
            if compensation.target.exists():
                compensation.target.rmdir()
        elif kind is _CompensationKind.MAKE_PARENT:
            compensation.target.mkdir()
        elif kind is _CompensationKind.MOVE_PATH:
            assert compensation.other is not None
            os.replace(compensation.target, compensation.other)
        elif kind is _CompensationKind.RECREATE_LINK:
            assert compensation.other is not None
            if os.path.lexists(compensation.target):
                self.backend.remove_link(compensation.target)
            self._recreate(compensation.other, compensation.target, compensation.is_directory)
        elif kind is _CompensationKind.RESTORE_RECEIPT:
            assert compensation.payload is not None
            compensation.target.write_bytes(compensation.payload)
        elif kind is _CompensationKind.DELETE_RECEIPT:
            compensation.target.unlink(missing_ok=True)

    def _recreate(self, source: Path, destination: Path, is_directory: bool) -> None:
        if is_directory:
            self.backend.create_directory_link(source, destination)
        else:
            self.backend.create_file_link(source, destination)


class _InstallRun(_Transaction):
    """Accumulates events and a typed compensation journal for one install."""

    def __init__(self, backend: LinkBackend) -> None:
        super().__init__(backend)
        self.backups: list[ReceiptBackup] = []
        self.created_parents: list[Path] = []

    def execute(self, action: PlannedAction) -> None:
        if action.kind is ActionKind.BACKUP:
            self._backup(action)
        elif action.kind is ActionKind.CREATE_LINK:
            self._create(action)
        elif action.kind is ActionKind.REPLACE_LINK:
            self._replace(action)
        else:  # pragma: no cover - defensive
            raise ValueError(f"unsupported action kind: {action.kind}")

    def write_receipt(self, receipt: InstallReceipt, receipt_file: Path) -> None:
        self._ensure_parents(receipt_file, record_projection_parent=False, emit_event=False)
        if receipt_file.exists():
            prior = receipt_file.read_bytes()
            self.journal.append(_Compensation(_CompensationKind.RESTORE_RECEIPT, receipt_file, payload=prior))
        else:
            self.journal.append(_Compensation(_CompensationKind.DELETE_RECEIPT, receipt_file))
        write_receipt_atomic(receipt, receipt_file)
        self.events.append(ExecutionEvent(ExecutionEventKind.WROTE_RECEIPT, receipt_file))

    def _backup(self, action: PlannedAction) -> None:
        original, backup = action.source, action.destination
        digest = file_sha256(original)
        os.replace(original, backup)
        self.journal.append(_Compensation(_CompensationKind.MOVE_PATH, backup, other=original))
        self.backups.append(ReceiptBackup(original=original, backup=backup, sha256=digest))
        self.events.append(ExecutionEvent(ExecutionEventKind.BACKED_UP, original))

    def _create(self, action: PlannedAction) -> None:
        self._ensure_parents(action.destination, record_projection_parent=True, emit_event=True)
        self._link(action.source, action.destination, action.is_directory)
        self.journal.append(
            _Compensation(_CompensationKind.REMOVE_LINK, action.destination, is_directory=action.is_directory)
        )

    def _replace(self, action: PlannedAction) -> None:
        destination = action.destination
        old_target = self.backend.resolved_target(destination)
        self.backend.remove_link(destination)
        self.events.append(ExecutionEvent(ExecutionEventKind.REMOVED_STALE_LINK, destination))
        self.journal.append(
            _Compensation(
                _CompensationKind.RECREATE_LINK,
                destination,
                other=old_target,
                is_directory=action.is_directory,
            )
        )
        self._link(action.source, destination, action.is_directory)

    def _link(self, source: Path, destination: Path, is_directory: bool) -> None:
        if is_directory:
            self.backend.create_directory_link(source, destination)
        else:
            self.backend.create_file_link(source, destination)
        self.events.append(ExecutionEvent(ExecutionEventKind.CREATED_LINK, destination))

    def _ensure_parents(self, target: Path, *, record_projection_parent: bool, emit_event: bool) -> None:
        missing: list[Path] = []
        node = target.parent
        while not node.exists():
            missing.append(node)
            node = node.parent
        for parent in reversed(missing):
            parent.mkdir()
            self.journal.append(_Compensation(_CompensationKind.REMOVE_PARENT, parent))
            if record_projection_parent:
                self.created_parents.append(parent)
            if emit_event:
                self.events.append(ExecutionEvent(ExecutionEventKind.CREATED_PARENT, parent))


class _UninstallRun(_Transaction):
    """Executes an uninstall plan action-by-action with a reversible journal."""

    def execute(self, action: UninstallAction, next_receipt: InstallReceipt | None, receipt_file: Path) -> None:
        if action.kind is UninstallActionKind.REMOVE_LINK:
            self._remove_link(action.destination)
        elif action.kind is UninstallActionKind.RESTORE_BACKUP:
            self._restore_backup(action)
        elif action.kind is UninstallActionKind.REMOVE_EMPTY_PARENT:
            self._remove_parent(action.destination)
        elif action.kind is UninstallActionKind.REPLACE_RECEIPT:
            assert next_receipt is not None
            self._replace_receipt(next_receipt, receipt_file)
        elif action.kind is UninstallActionKind.DELETE_RECEIPT:
            self._delete_receipt(receipt_file)
        else:  # pragma: no cover - defensive
            raise ValueError(f"unsupported uninstall action kind: {action.kind}")

    def _remove_link(self, destination: Path) -> None:
        is_directory = destination.is_dir()
        old_target = self.backend.resolved_target(destination)
        self.backend.remove_link(destination)
        self.journal.append(
            _Compensation(_CompensationKind.RECREATE_LINK, destination, other=old_target, is_directory=is_directory)
        )
        self.events.append(ExecutionEvent(ExecutionEventKind.REMOVED_LINK, destination))

    def _restore_backup(self, action: UninstallAction) -> None:
        assert action.source is not None
        backup, original = action.source, action.destination
        os.replace(backup, original)
        self.journal.append(_Compensation(_CompensationKind.MOVE_PATH, original, other=backup))
        self.events.append(ExecutionEvent(ExecutionEventKind.RESTORED_BACKUP, original))

    def _remove_parent(self, parent: Path) -> None:
        parent.rmdir()
        self.journal.append(_Compensation(_CompensationKind.MAKE_PARENT, parent))
        self.events.append(ExecutionEvent(ExecutionEventKind.REMOVED_EMPTY_PARENT, parent))

    def _replace_receipt(self, receipt: InstallReceipt, receipt_file: Path) -> None:
        prior = receipt_file.read_bytes()
        self.journal.append(_Compensation(_CompensationKind.RESTORE_RECEIPT, receipt_file, payload=prior))
        write_receipt_atomic(receipt, receipt_file)
        self.events.append(ExecutionEvent(ExecutionEventKind.WROTE_RECEIPT, receipt_file))

    def _delete_receipt(self, receipt_file: Path) -> None:
        prior = receipt_file.read_bytes()
        self.journal.append(_Compensation(_CompensationKind.RESTORE_RECEIPT, receipt_file, payload=prior))
        receipt_file.unlink()
        self.events.append(ExecutionEvent(ExecutionEventKind.DELETED_RECEIPT, receipt_file))


def _has_file_link_action(plan: InstallPlan) -> bool:
    return any(action.kind in _LINK_ACTIONS and not action.is_directory for action in plan.actions)


def _build_receipt(
    plan: InstallPlan,
    root: AgentRoot,
    existing: InstallReceipt | None,
    run: _InstallRun,
    projection_by_destination: dict[Path, Projection],
) -> InstallReceipt:
    owned: dict[Path, ReceiptProjection] = {}
    if existing is not None:
        for projection in existing.projections:
            owned[projection.destination] = projection

    for finding in plan.findings:
        # A CORRECT finding for a per-skill link carries the *parent* skills projection,
        # so preserve the already-recorded child source/kind and only widen the harness set.
        if finding.state is FindingState.CORRECT and finding.path in owned:
            current = owned[finding.path]
            owned[finding.path] = replace(
                current, harnesses=_merge_harnesses(current.harnesses, finding.projection.harnesses)
            )

    for action in plan.actions:
        if action.kind not in _LINK_ACTIONS:
            continue
        plan_projection = projection_by_destination[action.destination]
        owned_projection = owned.get(action.destination)
        existing_harnesses = owned_projection.harnesses if owned_projection is not None else ()
        owned[action.destination] = ReceiptProjection(
            destination=action.destination,
            source=action.source,
            kind=plan_projection.kind,
            harnesses=_merge_harnesses(existing_harnesses, plan_projection.harnesses),
        )

    projections = tuple(owned[destination] for destination in sorted(owned, key=Path.as_posix))
    backups = (existing.backups if existing is not None else ()) + tuple(run.backups)
    parents = _merge_parents(existing.created_parents if existing is not None else (), run.created_parents)
    return InstallReceipt(
        schema_version=RECEIPT_SCHEMA_VERSION,
        root_identity=root.identity,
        installed_root=root.path,
        projections=projections,
        backups=backups,
        created_parents=parents,
    )


def _merge_harnesses(current: tuple[Harness, ...], incoming: tuple[Harness, ...]) -> tuple[Harness, ...]:
    present = set(current) | set(incoming)
    return tuple(harness for harness in _HARNESS_ORDER if harness in present)


def _merge_parents(existing: tuple[Path, ...], new: list[Path]) -> tuple[Path, ...]:
    merged = list(existing)
    for parent in new:
        if parent not in merged:
            merged.append(parent)
    return tuple(merged)
