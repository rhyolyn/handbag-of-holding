"""Journaled install execution with rollback and post-install validation."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Literal, NoReturn, assert_never

from .executor_errors import BackupPathOccupied, RollbackFailure
from .executor_errors import ExecutionError as ExecutionError
from .harness_profiles import InstructionsMapping
from .link_errors import PartialLinkCleanupFailed
from .links import LinkBackend
from .models import (
    AgentRoot,
    ExecutionEvent,
    ExecutionEventKind,
    ExecutionReport,
    Harness,
)
from .planning import (
    BackupFile,
    CreateLink,
    DeleteReceipt,
    InstallChange,
    InstallPlan,
    InstallState,
    PathStatus,
    RemovalChange,
    RemoveDirectory,
    RemoveLink,
    ReplaceLink,
    RestoreFile,
    UninstallPlan,
    WriteReceipt,
)
from .receipts import (
    RECEIPT_SCHEMA_VERSION,
    InstallReceipt,
    OwnedBackup,
    OwnedLink,
    file_sha256,
    write_receipt_atomic,
)

_HARNESS_ORDER = (Harness.CODEX, Harness.CLAUDE, Harness.COPILOT)


def _is_directory_mapping(mapping: object) -> bool:
    return not isinstance(mapping, InstructionsMapping)


def apply_install_plan(
    plan: InstallPlan,
    root: AgentRoot,
    probe_root: Path,
    backend: LinkBackend,
    receipt_file: Path,
    existing_receipt: InstallReceipt | None,
) -> ExecutionReport:
    """Execute an applicable plan transactionally, rolling back every mutation on failure."""
    if plan.is_blocked:
        raise ValueError("cannot apply a blocked install plan")
    if not plan.changes and existing_receipt is None:
        return ExecutionReport(events=(), receipt=None, receipt_written=False)

    run = _InstallRun(backend)

    if _has_file_link_change(plan):
        backend.probe_file_link_capability(probe_root)
        run.events.append(ExecutionEvent(ExecutionEventKind.PROBED_CAPABILITY, probe_root))

    try:
        for change in plan.changes:
            run.execute(change)
        validation = validate_installed_plan(plan, backend)
        if any(status.state is not InstallState.CURRENT for status in validation):
            raise _FinalValidationFailed(validation)

        receipt = _build_receipt(plan, root, existing_receipt, run)
        if existing_receipt is None or receipt != existing_receipt:
            run.write_receipt(receipt, receipt_file)
            return ExecutionReport(tuple(run.events), receipt, True)
        return ExecutionReport(tuple(run.events), existing_receipt, False)
    except BaseException as original:
        _finalize_failure("install", original, run)


def validate_installed_plan(plan: InstallPlan, backend: LinkBackend) -> tuple[PathStatus, ...]:
    """Re-check every mutated link and report CURRENT or a mismatch state."""
    statuses: list[PathStatus] = []
    for change in plan.changes:
        if not isinstance(change, (CreateLink, ReplaceLink)):
            continue
        mapping = change.mapping
        resolved = backend.resolved_target(mapping.destination)
        state = InstallState.CURRENT if resolved == mapping.source.resolve() else InstallState.STALE_LINK
        statuses.append(PathStatus(state, mapping))
    return tuple(statuses)


def apply_uninstall_plan(plan: UninstallPlan, backend: LinkBackend) -> ExecutionReport:
    """Execute an applicable uninstall plan transactionally, rolling back on failure.

    The receipt path travels inside the plan's WriteReceipt/DeleteReceipt change, so
    this entrypoint no longer accepts a competing receipt-file argument.
    """
    if plan.is_blocked:
        raise ValueError("cannot apply a blocked uninstall plan")
    if not plan.changes:
        return ExecutionReport(events=(), receipt=None, receipt_written=False)

    run = _UninstallRun(backend)
    try:
        for change in plan.changes:
            run.execute(change)
        written = next((change for change in plan.changes if isinstance(change, WriteReceipt)), None)
        return ExecutionReport(
            tuple(run.events),
            written.receipt if written is not None else None,
            written is not None,
        )
    except BaseException as original:
        _finalize_failure("uninstall", original, run)


class _FinalValidationFailed(Exception):
    def __init__(self, statuses: tuple[PathStatus, ...]) -> None:
        self.statuses = statuses
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


def _finalize_failure(
    operation: Literal["install", "uninstall"], original: BaseException, run: _Transaction
) -> NoReturn:
    failures, rollback_recoverable = run.rollback()
    recoverable = _recoverable_paths(original, rollback_recoverable)
    if isinstance(original, BackupPathOccupied) and not failures:
        raise original
    if isinstance(original, Exception):
        raise ExecutionError(operation, original, failures, recoverable) from original
    if failures:
        original.add_note(_rollback_failure_note(operation, failures, recoverable))
    raise original


def _rollback_failure_note(
    operation: Literal["install", "uninstall"],
    failures: tuple[RollbackFailure, ...],
    recoverable_paths: tuple[Path, ...],
) -> str:
    paths = ", ".join(str(path) for path in recoverable_paths)
    details = "; ".join(f"{failure.operation} {failure.path}: {failure.detail}" for failure in failures)
    return (
        f"{operation} rollback left {len(recoverable_paths)} path(s) needing manual recovery: {paths}. "
        f"Rollback failures: {details}"
    )


class _InstallRun(_Transaction):
    """Accumulates events and a typed compensation journal for one install."""

    def __init__(self, backend: LinkBackend) -> None:
        super().__init__(backend)
        self.backups: list[OwnedBackup] = []
        self.created_parents: list[Path] = []

    def execute(self, change: InstallChange) -> None:
        if isinstance(change, BackupFile):
            self._backup(change)
        elif isinstance(change, CreateLink):
            self._create(change)
        elif isinstance(change, ReplaceLink):
            self._replace(change)
        else:  # pragma: no cover - defensive
            assert_never(change)

    def write_receipt(self, receipt: InstallReceipt, receipt_file: Path) -> None:
        self._ensure_parents(receipt_file, record_projection_parent=False, emit_event=False)
        if receipt_file.exists():
            prior = receipt_file.read_bytes()
            self.journal.append(_Compensation(_CompensationKind.RESTORE_RECEIPT, receipt_file, payload=prior))
        else:
            self.journal.append(_Compensation(_CompensationKind.DELETE_RECEIPT, receipt_file))
        write_receipt_atomic(receipt, receipt_file)
        self.events.append(ExecutionEvent(ExecutionEventKind.WROTE_RECEIPT, receipt_file))

    def _backup(self, change: BackupFile) -> None:
        original, backup = change.original, change.backup
        try:
            descriptor = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise BackupPathOccupied(backup) from exc

        try:
            os.close(descriptor)
            digest = file_sha256(original)
            os.replace(original, backup)
        except BaseException as original_error:
            try:
                backup.unlink(missing_ok=True)
            except Exception as cleanup_error:
                original_error.add_note(
                    f"failed to remove reserved backup path {backup} after backup failure: {cleanup_error}"
                )
            raise
        self.journal.append(_Compensation(_CompensationKind.MOVE_PATH, backup, other=original))
        self.backups.append(OwnedBackup(original=original, backup=backup, sha256=digest))
        self.events.append(ExecutionEvent(ExecutionEventKind.BACKED_UP, original))

    def _create(self, change: CreateLink) -> None:
        mapping = change.mapping
        is_directory = _is_directory_mapping(mapping)
        self._ensure_parents(mapping.destination, record_projection_parent=True, emit_event=True)
        self._link(mapping.source, mapping.destination, is_directory)
        self.journal.append(
            _Compensation(_CompensationKind.REMOVE_LINK, mapping.destination, is_directory=is_directory)
        )

    def _replace(self, change: ReplaceLink) -> None:
        mapping = change.mapping
        is_directory = _is_directory_mapping(mapping)
        destination = mapping.destination
        old_target = self.backend.resolved_target(destination)
        self.backend.remove_link(destination)
        self.events.append(ExecutionEvent(ExecutionEventKind.REMOVED_STALE_LINK, destination))
        self.journal.append(
            _Compensation(
                _CompensationKind.RECREATE_LINK,
                destination,
                other=old_target,
                is_directory=is_directory,
            )
        )
        self._link(mapping.source, destination, is_directory)

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
    """Executes an uninstall plan change-by-change with a reversible journal."""

    def execute(self, change: RemovalChange) -> None:
        if isinstance(change, RemoveLink):
            self._remove_link(change.link)
        elif isinstance(change, RestoreFile):
            self._restore_backup(change.backup)
        elif isinstance(change, RemoveDirectory):
            self._remove_parent(change.path)
        elif isinstance(change, WriteReceipt):
            self._replace_receipt(change.receipt, change.path)
        elif isinstance(change, DeleteReceipt):
            self._delete_receipt(change.path)
        else:  # pragma: no cover - defensive
            assert_never(change)

    def _remove_link(self, link: OwnedLink) -> None:
        destination = link.mapping.destination
        is_directory = _is_directory_mapping(link.mapping)
        old_target = self.backend.resolved_target(destination)
        self.backend.remove_link(destination)
        self.journal.append(
            _Compensation(_CompensationKind.RECREATE_LINK, destination, other=old_target, is_directory=is_directory)
        )
        self.events.append(ExecutionEvent(ExecutionEventKind.REMOVED_LINK, destination))

    def _restore_backup(self, backup: OwnedBackup) -> None:
        os.replace(backup.backup, backup.original)
        self.journal.append(_Compensation(_CompensationKind.MOVE_PATH, backup.original, other=backup.backup))
        self.events.append(ExecutionEvent(ExecutionEventKind.RESTORED_BACKUP, backup.original))

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


def _has_file_link_change(plan: InstallPlan) -> bool:
    return any(
        isinstance(change, (CreateLink, ReplaceLink)) and not _is_directory_mapping(change.mapping)
        for change in plan.changes
    )


def _recoverable_paths(original: BaseException, rollback_recoverable: tuple[Path, ...]) -> tuple[Path, ...]:
    recoverable: list[Path] = []
    if isinstance(original, PartialLinkCleanupFailed):
        recoverable.append(original.recoverable_path)
    for path in rollback_recoverable:
        if path not in recoverable:
            recoverable.append(path)
    return tuple(recoverable)


def _build_receipt(
    plan: InstallPlan,
    root: AgentRoot,
    existing: InstallReceipt | None,
    run: _InstallRun,
) -> InstallReceipt:
    owned: dict[Path, OwnedLink] = {}
    if existing is not None:
        for link in existing.links:
            owned[link.mapping.destination] = link

    for status in plan.statuses:
        # A CURRENT status for an already-owned link only widens its harness set;
        # its concrete mapping already carries the correct source and destination.
        if status.state is InstallState.CURRENT and status.path in owned:
            current = owned[status.path].mapping
            merged = _merge_harnesses(current.harnesses, status.mapping.harnesses)
            owned[status.path] = OwnedLink(replace(current, harnesses=merged))

    for change in plan.changes:
        if not isinstance(change, (CreateLink, ReplaceLink)):
            continue
        mapping = change.mapping
        existing_link = owned.get(mapping.destination)
        existing_harnesses = existing_link.mapping.harnesses if existing_link is not None else ()
        merged = _merge_harnesses(existing_harnesses, mapping.harnesses)
        owned[mapping.destination] = OwnedLink(replace(mapping, harnesses=merged))

    links = tuple(owned[destination] for destination in sorted(owned, key=Path.as_posix))
    backups = (existing.backups if existing is not None else ()) + tuple(run.backups)
    parents = _merge_parents(existing.created_parents if existing is not None else (), run.created_parents)
    return InstallReceipt(
        schema_version=RECEIPT_SCHEMA_VERSION,
        root_identity=root.identity,
        installed_root=root.path,
        links=links,
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
