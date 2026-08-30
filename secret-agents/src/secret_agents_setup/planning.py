"""Read-only filesystem classification and install/uninstall plan construction."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from .harness_profiles import InstallMapping, SkillsMapping
from .links import LinkBackend
from .models import (
    Harness,
    SkillDescriptor,
    UninstallAction,
    UninstallActionKind,
    UninstallFinding,
    UninstallFindingState,
    UninstallPlan,
)
from .path_safety import is_path_within
from .receipts import InstallReceipt, OwnedBackup, OwnedLink, file_sha256, receipt_path

_HARNESS_ORDER = (Harness.CODEX, Harness.CLAUDE, Harness.COPILOT)


class InstallState(StrEnum):
    CURRENT = "current"
    MISSING = "missing"
    STALE_LINK = "stale-link"
    BROKEN_LINK = "broken-link"
    COMPATIBLE_SKILLS_DIRECTORY = "compatible-skills-directory"
    BACKUP_PLANNED = "backup-planned"
    CONFLICT = "conflict"
    SKILL_NAME_COLLISION = "skill-name-collision"

    @property
    def output_name(self) -> str:
        """The stable stdout token for this state, preserved across the redesign."""
        return _INSTALL_OUTPUT_NAMES[self]

    @property
    def blocks_install(self) -> bool:
        return self in _BLOCKING_INSTALL_STATES


_INSTALL_OUTPUT_NAMES: dict[InstallState, str] = {
    InstallState.CURRENT: "correct",
    InstallState.MISSING: "missing",
    InstallState.STALE_LINK: "stale-link",
    InstallState.BROKEN_LINK: "broken-link",
    InstallState.COMPATIBLE_SKILLS_DIRECTORY: "compatible-skill-directory",
    InstallState.BACKUP_PLANNED: "unrelated",
    InstallState.CONFLICT: "unrelated",
    InstallState.SKILL_NAME_COLLISION: "skill-name-collision",
}
_BLOCKING_INSTALL_STATES = frozenset({InstallState.CONFLICT, InstallState.SKILL_NAME_COLLISION})


@dataclass(frozen=True)
class PathStatus:
    state: InstallState
    mapping: InstallMapping

    @property
    def path(self) -> Path:
        return self.mapping.destination

    @property
    def blocks_install(self) -> bool:
        return self.state.blocks_install


@dataclass(frozen=True)
class CreateLink:
    mapping: InstallMapping


@dataclass(frozen=True)
class ReplaceLink:
    mapping: InstallMapping


@dataclass(frozen=True)
class BackupFile:
    original: Path
    backup: Path


InstallChange = CreateLink | ReplaceLink | BackupFile


@dataclass(frozen=True)
class InstallPlan:
    statuses: tuple[PathStatus, ...]
    changes: tuple[InstallChange, ...]

    @property
    def is_blocked(self) -> bool:
        return any(status.blocks_install for status in self.statuses)


def build_install_plan(
    mappings: tuple[InstallMapping, ...],
    catalog: tuple[SkillDescriptor, ...],
    backup_conflicts: bool,
    timestamp: datetime,
) -> InstallPlan:
    """Classify current mapping state without mutating it and plan safe changes."""
    statuses: list[PathStatus] = []
    changes: list[InstallChange] = []

    sorted_catalog = tuple(sorted(catalog, key=lambda skill: skill.name))
    for mapping in sorted(mappings, key=lambda item: item.destination.as_posix()):
        mapping_statuses, mapping_changes = _classify_mapping(
            mapping,
            sorted_catalog,
            backup_conflicts,
            timestamp,
        )
        statuses.extend(mapping_statuses)
        changes.extend(mapping_changes)

    if any(status.blocks_install for status in statuses):
        changes.clear()
    return InstallPlan(statuses=tuple(statuses), changes=tuple(changes))


def _classify_mapping(
    mapping: InstallMapping,
    catalog: tuple[SkillDescriptor, ...],
    backup_conflicts: bool,
    timestamp: datetime,
) -> tuple[list[PathStatus], list[InstallChange]]:
    destination = mapping.destination
    if not os.path.lexists(destination):
        return [PathStatus(InstallState.MISSING, mapping)], [CreateLink(mapping)]

    if _is_link(destination):
        return _classify_whole_link(mapping)

    if isinstance(mapping, SkillsMapping) and destination.is_dir():
        return _classify_skill_directory(mapping, catalog)

    can_backup = backup_conflicts and not isinstance(mapping, SkillsMapping) and destination.is_file()
    if not can_backup:
        return [PathStatus(InstallState.CONFLICT, mapping)], []

    backup = _available_backup_path(destination, timestamp)
    return [PathStatus(InstallState.BACKUP_PLANNED, mapping)], [
        BackupFile(destination, backup),
        CreateLink(mapping),
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
    mapping: InstallMapping,
) -> tuple[list[PathStatus], list[InstallChange]]:
    destination = mapping.destination
    if not destination.exists():
        state = InstallState.BROKEN_LINK
    elif _same_target(destination, mapping.source):
        return [PathStatus(InstallState.CURRENT, mapping)], []
    else:
        state = InstallState.STALE_LINK

    return [PathStatus(state, mapping)], [ReplaceLink(mapping)]


def _classify_skill_directory(
    mapping: SkillsMapping, catalog: tuple[SkillDescriptor, ...]
) -> tuple[list[PathStatus], list[InstallChange]]:
    statuses = [PathStatus(InstallState.COMPATIBLE_SKILLS_DIRECTORY, mapping)]
    changes: list[InstallChange] = []

    for skill in catalog:
        child_destination = mapping.destination / skill.name
        # Each per-skill link is its own SkillsMapping so every status and change
        # reports the real source and destination, not the parent collection.
        child = SkillsMapping(harnesses=mapping.harnesses, source=skill.directory, destination=child_destination)
        if not os.path.lexists(child_destination):
            statuses.append(PathStatus(InstallState.MISSING, child))
            changes.append(CreateLink(child))
        elif _is_current_link(child_destination, skill.directory):
            statuses.append(PathStatus(InstallState.CURRENT, child))
        else:
            statuses.append(PathStatus(InstallState.SKILL_NAME_COLLISION, child))

    return statuses, changes


def _is_current_link(destination: Path, source: Path) -> bool:
    return _is_link(destination) and destination.exists() and _same_target(destination, source)


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
    retained_links: list[OwnedLink] = []

    if receipt.root_identity != expected_identity:
        findings.append(UninstallFinding(UninstallFindingState.FOREIGN_CONTENT, receipt.installed_root, blocking=True))

    for link in receipt.links:
        _classify_uninstall_link(
            link, selected, backend, home, findings, remove_links, removed_destinations, retained_links
        )

    restores, retained_backups = _classify_backups(receipt.backups, home, removed_destinations, findings)
    parent_removals, retained_parents = _classify_parents(
        receipt.created_parents, home, remove_links, restores, findings
    )

    if any(finding.blocking for finding in findings):
        return UninstallPlan(tuple(findings), (), receipt)

    partial = bool(retained_links) or bool(retained_backups)
    receipt_file = receipt_path(home, expected_identity)
    next_receipt = _next_receipt(receipt, retained_links, retained_backups, retained_parents) if partial else None
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


def _classify_uninstall_link(
    link: OwnedLink,
    selected: set[Harness],
    backend: LinkBackend,
    home: Path,
    findings: list[UninstallFinding],
    remove_links: list[UninstallAction],
    removed_destinations: set[Path],
    retained_links: list[OwnedLink],
) -> None:
    mapping = link.mapping
    destination = mapping.destination
    if not is_path_within(destination, home, follow_leaf=False):
        findings.append(UninstallFinding(UninstallFindingState.FOREIGN_CONTENT, destination, blocking=True))
        retained_links.append(link)
        return

    remaining = tuple(harness for harness in mapping.harnesses if harness not in selected)
    if len(remaining) == len(mapping.harnesses):
        findings.append(UninstallFinding(UninstallFindingState.SHARED_RETAINED, destination))
        retained_links.append(link)
        return
    if remaining:
        findings.append(UninstallFinding(UninstallFindingState.SHARED_RETAINED, destination))
        retained_links.append(OwnedLink(replace(mapping, harnesses=remaining)))
        return

    if not os.path.lexists(destination):
        findings.append(UninstallFinding(UninstallFindingState.MISSING_OWNED_LINK, destination))
        return
    if backend.resolved_target(destination) == mapping.source.resolve():
        findings.append(UninstallFinding(UninstallFindingState.OWNED, destination))
        remove_links.append(UninstallAction(UninstallActionKind.REMOVE_LINK, None, destination))
        removed_destinations.add(destination)
    else:
        findings.append(UninstallFinding(UninstallFindingState.FOREIGN_CONTENT, destination, blocking=True))
        retained_links.append(link)


def _classify_backups(
    backups: tuple[OwnedBackup, ...],
    home: Path,
    removed_destinations: set[Path],
    findings: list[UninstallFinding],
) -> tuple[list[UninstallAction], list[OwnedBackup]]:
    restores: list[UninstallAction] = []
    retained: list[OwnedBackup] = []
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
    links: list[OwnedLink],
    backups: list[OwnedBackup],
    parents: list[Path],
) -> InstallReceipt:
    return InstallReceipt(
        schema_version=receipt.schema_version,
        root_identity=receipt.root_identity,
        installed_root=receipt.installed_root,
        links=tuple(sorted(links, key=lambda link: link.mapping.destination.as_posix())),
        backups=tuple(backups),
        created_parents=tuple(parents),
    )


def _selected_harnesses(harnesses: tuple[Harness, ...]) -> set[Harness]:
    if Harness.ALL in harnesses:
        return set(_HARNESS_ORDER)
    return {harness for harness in harnesses if harness in _HARNESS_ORDER}
