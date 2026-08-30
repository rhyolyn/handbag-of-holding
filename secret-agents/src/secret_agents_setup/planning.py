"""Read-only filesystem classification and install/uninstall plan construction."""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from .links import LinkBackend
from .models import (
    ActionKind,
    Finding,
    FindingState,
    Harness,
    InstallPlan,
    InstallReceipt,
    PlannedAction,
    Projection,
    ProjectionKind,
    ReceiptBackup,
    ReceiptProjection,
    SkillDescriptor,
    UninstallAction,
    UninstallActionKind,
    UninstallFinding,
    UninstallFindingState,
    UninstallPlan,
)
from .path_safety import is_path_within
from .receipts import file_sha256, receipt_path

_HARNESS_ORDER = (Harness.CODEX, Harness.CLAUDE, Harness.COPILOT)


def build_install_plan(
    projections: tuple[Projection, ...],
    catalog: tuple[SkillDescriptor, ...],
    backup_conflicts: bool,
    timestamp: datetime,
) -> InstallPlan:
    """Classify current projection state without mutating it and plan safe actions."""
    findings: list[Finding] = []
    actions: list[PlannedAction] = []

    sorted_catalog = tuple(sorted(catalog, key=lambda skill: skill.name))
    for projection in sorted(projections, key=lambda item: item.destination.as_posix()):
        projection_findings, projection_actions = _classify_projection(
            projection,
            sorted_catalog,
            backup_conflicts,
            timestamp,
        )
        findings.extend(projection_findings)
        actions.extend(projection_actions)

    if any(finding.blocking for finding in findings):
        actions.clear()
    return InstallPlan(findings=tuple(findings), actions=tuple(actions))


def _classify_projection(
    projection: Projection,
    catalog: tuple[SkillDescriptor, ...],
    backup_conflicts: bool,
    timestamp: datetime,
) -> tuple[list[Finding], list[PlannedAction]]:
    destination = projection.destination
    if not os.path.lexists(destination):
        return [
            Finding(FindingState.MISSING, destination, projection),
        ], [
            _link_action(ActionKind.CREATE_LINK, projection.source, destination, projection),
        ]

    if _is_link(destination):
        return _classify_whole_link(projection)

    if projection.kind is ProjectionKind.SKILLS and destination.is_dir():
        return _classify_skill_directory(projection, catalog)

    can_backup = backup_conflicts and projection.kind is ProjectionKind.GUIDANCE and destination.is_file()
    finding = Finding(FindingState.UNRELATED, destination, projection, blocking=not can_backup)
    if not can_backup:
        return [finding], []

    backup = _available_backup_path(destination, timestamp)
    return [finding], [
        PlannedAction(ActionKind.BACKUP, destination, backup, False),
        _link_action(ActionKind.CREATE_LINK, projection.source, destination, projection),
    ]


def _available_backup_path(original: Path, timestamp: datetime) -> Path:
    timestamped = original.with_name(f"{original.name}.backup-{timestamp.strftime('%Y%m%d-%H%M%S')}")
    candidate = timestamped
    suffix = 2
    while os.path.lexists(candidate):
        candidate = timestamped.with_name(f"{timestamped.name}-{suffix}")
        suffix += 1
    return candidate


def _classify_whole_link(
    projection: Projection,
) -> tuple[list[Finding], list[PlannedAction]]:
    destination = projection.destination
    if not destination.exists():
        state = FindingState.BROKEN_LINK
    elif _same_target(destination, projection.source):
        return [Finding(FindingState.CORRECT, destination, projection)], []
    else:
        state = FindingState.STALE_LINK

    return [Finding(state, destination, projection)], [
        _link_action(ActionKind.REPLACE_LINK, projection.source, destination, projection),
    ]


def _classify_skill_directory(
    projection: Projection, catalog: tuple[SkillDescriptor, ...]
) -> tuple[list[Finding], list[PlannedAction]]:
    findings = [Finding(FindingState.COMPATIBLE_SKILL_DIRECTORY, projection.destination, projection)]
    actions: list[PlannedAction] = []

    for skill in catalog:
        destination = projection.destination / skill.name
        if not os.path.lexists(destination):
            findings.append(Finding(FindingState.MISSING, destination, projection))
            actions.append(PlannedAction(ActionKind.CREATE_LINK, skill.directory, destination, True))
        elif _is_link(destination) and destination.exists() and _same_target(destination, skill.directory):
            findings.append(Finding(FindingState.CORRECT, destination, projection))
        else:
            findings.append(Finding(FindingState.SKILL_NAME_COLLISION, destination, projection, blocking=True))

    return findings, actions


def _link_action(kind: ActionKind, source: Path, destination: Path, projection: Projection) -> PlannedAction:
    return PlannedAction(kind, source, destination, projection.is_directory)


def _same_target(destination: Path, source: Path) -> bool:
    return destination.resolve(strict=False) == source.resolve(strict=False)


def _is_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction is not None and is_junction())


def build_uninstall_plan(
    receipt: InstallReceipt | None,
    harnesses: tuple[Harness, ...],
    backend: LinkBackend,
    *,
    expected_identity: str,
    home: Path,
) -> UninstallPlan:
    """Classify a receipt against the current filesystem and plan a safe, reversible removal."""
    if receipt is None:
        return UninstallPlan(
            findings=(UninstallFinding(UninstallFindingState.NOT_INSTALLED, home),),
            actions=(),
            next_receipt=None,
        )

    selected = _selected_harnesses(harnesses)
    findings: list[UninstallFinding] = []
    remove_links: list[UninstallAction] = []
    removed_destinations: set[Path] = set()
    retained_projections: list[ReceiptProjection] = []

    if receipt.root_identity != expected_identity:
        findings.append(UninstallFinding(UninstallFindingState.FOREIGN_CONTENT, receipt.installed_root, blocking=True))

    for projection in receipt.projections:
        _classify_uninstall_projection(
            projection, selected, backend, home, findings, remove_links, removed_destinations, retained_projections
        )

    restores, retained_backups = _classify_backups(receipt.backups, home, removed_destinations, findings)
    parent_removals, retained_parents = _classify_parents(
        receipt.created_parents, home, remove_links, restores, findings
    )

    if any(finding.blocking for finding in findings):
        return UninstallPlan(tuple(findings), (), receipt)

    partial = bool(retained_projections) or bool(retained_backups)
    receipt_file = receipt_path(home, expected_identity)
    next_receipt = _next_receipt(receipt, retained_projections, retained_backups, retained_parents) if partial else None
    receipt_action = UninstallAction(
        UninstallActionKind.REPLACE_RECEIPT if partial else UninstallActionKind.DELETE_RECEIPT,
        None,
        receipt_file,
    )

    actions = (
        *sorted(remove_links, key=lambda action: action.destination.as_posix()),
        *sorted(restores, key=lambda action: action.destination.as_posix()),
        *parent_removals,
        receipt_action,
    )
    return UninstallPlan(tuple(findings), actions, next_receipt)


def _classify_uninstall_projection(
    projection: ReceiptProjection,
    selected: set[Harness],
    backend: LinkBackend,
    home: Path,
    findings: list[UninstallFinding],
    remove_links: list[UninstallAction],
    removed_destinations: set[Path],
    retained_projections: list[ReceiptProjection],
) -> None:
    destination = projection.destination
    if not is_path_within(destination, home, follow_leaf=False):
        findings.append(UninstallFinding(UninstallFindingState.FOREIGN_CONTENT, destination, blocking=True))
        retained_projections.append(projection)
        return

    remaining = tuple(harness for harness in projection.harnesses if harness not in selected)
    if len(remaining) == len(projection.harnesses):
        findings.append(UninstallFinding(UninstallFindingState.SHARED_RETAINED, destination))
        retained_projections.append(projection)
        return
    if remaining:
        findings.append(UninstallFinding(UninstallFindingState.SHARED_RETAINED, destination))
        retained_projections.append(replace(projection, harnesses=remaining))
        return

    if not os.path.lexists(destination):
        findings.append(UninstallFinding(UninstallFindingState.MISSING_OWNED_LINK, destination))
        return
    if backend.resolved_target(destination) == projection.source.resolve():
        findings.append(UninstallFinding(UninstallFindingState.OWNED, destination))
        remove_links.append(UninstallAction(UninstallActionKind.REMOVE_LINK, None, destination))
        removed_destinations.add(destination)
    else:
        findings.append(UninstallFinding(UninstallFindingState.FOREIGN_CONTENT, destination, blocking=True))
        retained_projections.append(projection)


def _classify_backups(
    backups: tuple[ReceiptBackup, ...],
    home: Path,
    removed_destinations: set[Path],
    findings: list[UninstallFinding],
) -> tuple[list[UninstallAction], list[ReceiptBackup]]:
    restores: list[UninstallAction] = []
    retained: list[ReceiptBackup] = []
    for backup in backups:
        if not is_path_within(backup.original, home, follow_leaf=False):
            findings.append(UninstallFinding(UninstallFindingState.FOREIGN_CONTENT, backup.original, blocking=True))
            retained.append(backup)
            continue
        if not is_path_within(backup.backup, home, follow_leaf=True):
            findings.append(UninstallFinding(UninstallFindingState.FOREIGN_CONTENT, backup.backup, blocking=True))
            retained.append(backup)
            continue
        if backup.original not in removed_destinations:
            retained.append(backup)
            continue
        if not backup.backup.exists():
            findings.append(UninstallFinding(UninstallFindingState.BACKUP_MISSING, backup.backup, blocking=True))
            retained.append(backup)
        elif file_sha256(backup.backup) != backup.sha256:
            findings.append(UninstallFinding(UninstallFindingState.BACKUP_MODIFIED, backup.backup, blocking=True))
            retained.append(backup)
        else:
            restores.append(UninstallAction(UninstallActionKind.RESTORE_BACKUP, backup.backup, backup.original))
    return restores, retained


def _classify_parents(
    created_parents: tuple[Path, ...],
    home: Path,
    remove_links: list[UninstallAction],
    restores: list[UninstallAction],
    findings: list[UninstallFinding],
) -> tuple[list[UninstallAction], list[Path]]:
    removals: list[UninstallAction] = []
    retained: list[Path] = []
    removed_names: dict[Path, set[str]] = {}
    for action in remove_links:
        removed_names.setdefault(action.destination.parent, set()).add(action.destination.name)
    restored_names: dict[Path, set[str]] = {}
    for action in restores:
        restored_names.setdefault(action.destination.parent, set()).add(action.destination.name)

    for parent in created_parents:
        if not is_path_within(parent, home, follow_leaf=True):
            findings.append(UninstallFinding(UninstallFindingState.FOREIGN_CONTENT, parent, blocking=True))
            retained.append(parent)
            continue
        if not parent.exists():
            continue
        current = {entry.name for entry in parent.iterdir()}
        after = (current - removed_names.get(parent, set())) | restored_names.get(parent, set())
        if after:
            findings.append(UninstallFinding(UninstallFindingState.PARENT_PRESERVED, parent))
            retained.append(parent)
        else:
            removals.append(UninstallAction(UninstallActionKind.REMOVE_EMPTY_PARENT, None, parent))

    removals.sort(key=lambda action: (-len(action.destination.parts), action.destination.as_posix()))
    return removals, retained


def _next_receipt(
    receipt: InstallReceipt,
    projections: list[ReceiptProjection],
    backups: list[ReceiptBackup],
    parents: list[Path],
) -> InstallReceipt:
    return InstallReceipt(
        schema_version=receipt.schema_version,
        root_identity=receipt.root_identity,
        installed_root=receipt.installed_root,
        projections=tuple(sorted(projections, key=lambda projection: projection.destination.as_posix())),
        backups=tuple(backups),
        created_parents=tuple(parents),
    )


def _selected_harnesses(harnesses: tuple[Harness, ...]) -> set[Harness]:
    if Harness.ALL in harnesses:
        return set(_HARNESS_ORDER)
    return {harness for harness in harnesses if harness in _HARNESS_ORDER}
