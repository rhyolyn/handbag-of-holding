"""Read-only filesystem classification and install/uninstall plan construction."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from .harness_profiles import InstallMapping, SkillsMapping
from .links import LinkBackend
from .models import Harness, SkillDescriptor
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


class RemovalState(StrEnum):
    NOT_INSTALLED = "not-installed"
    OWNED = "owned"
    MISSING_OWNED_LINK = "missing-owned-link"
    SHARED_RETAINED = "shared-retained"
    FOREIGN_CONTENT = "foreign-content"
    BACKUP_MISSING = "backup-missing"
    BACKUP_MODIFIED = "backup-modified"
    PARENT_PRESERVED = "parent-preserved"

    @property
    def blocks_removal(self) -> bool:
        return self in _BLOCKING_REMOVAL_STATES


_BLOCKING_REMOVAL_STATES = frozenset(
    {RemovalState.FOREIGN_CONTENT, RemovalState.BACKUP_MISSING, RemovalState.BACKUP_MODIFIED}
)


@dataclass(frozen=True)
class RemovalStatus:
    state: RemovalState
    path: Path

    @property
    def blocks_removal(self) -> bool:
        return self.state.blocks_removal


@dataclass(frozen=True)
class RemoveLink:
    link: OwnedLink


@dataclass(frozen=True)
class RestoreFile:
    backup: OwnedBackup


@dataclass(frozen=True)
class RemoveDirectory:
    path: Path


@dataclass(frozen=True)
class WriteReceipt:
    path: Path
    receipt: InstallReceipt


@dataclass(frozen=True)
class DeleteReceipt:
    path: Path


RemovalChange = RemoveLink | RestoreFile | RemoveDirectory | WriteReceipt | DeleteReceipt


@dataclass(frozen=True)
class UninstallPlan:
    statuses: tuple[RemovalStatus, ...]
    changes: tuple[RemovalChange, ...]

    @property
    def is_blocked(self) -> bool:
        return any(status.blocks_removal for status in self.statuses)


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
        return UninstallPlan(statuses=(RemovalStatus(RemovalState.NOT_INSTALLED, home),), changes=())

    selected = _selected_harnesses(harnesses)
    statuses: list[RemovalStatus] = []
    remove_links: list[RemoveLink] = []
    removed_destinations: set[Path] = set()
    retained_links: list[OwnedLink] = []

    if receipt.root_identity != expected_identity:
        statuses.append(RemovalStatus(RemovalState.FOREIGN_CONTENT, receipt.installed_root))

    for link in receipt.links:
        _classify_uninstall_link(
            link, selected, backend, home, statuses, remove_links, removed_destinations, retained_links
        )

    restores, retained_backups = _classify_backups(receipt.backups, home, removed_destinations, statuses)
    parent_removals, retained_parents = _classify_parents(
        receipt.created_parents, home, remove_links, restores, statuses
    )

    if any(status.blocks_removal for status in statuses):
        return UninstallPlan(tuple(statuses), ())

    receipt_file = receipt_path(home, expected_identity)
    partial = bool(retained_links) or bool(retained_backups)
    receipt_change: RemovalChange
    if partial:
        next_receipt = _next_receipt(receipt, retained_links, retained_backups, retained_parents)
        receipt_change = WriteReceipt(receipt_file, next_receipt)
    else:
        receipt_change = DeleteReceipt(receipt_file)

    changes: tuple[RemovalChange, ...] = (
        *sorted(remove_links, key=lambda change: change.link.mapping.destination.as_posix()),
        *sorted(restores, key=lambda change: change.backup.original.as_posix()),
        *parent_removals,
        receipt_change,
    )
    return UninstallPlan(tuple(statuses), changes)


def _classify_uninstall_link(
    link: OwnedLink,
    selected: set[Harness],
    backend: LinkBackend,
    home: Path,
    statuses: list[RemovalStatus],
    remove_links: list[RemoveLink],
    removed_destinations: set[Path],
    retained_links: list[OwnedLink],
) -> None:
    mapping = link.mapping
    destination = mapping.destination
    if not is_path_within(destination, home, follow_leaf=False):
        statuses.append(RemovalStatus(RemovalState.FOREIGN_CONTENT, destination))
        retained_links.append(link)
        return

    remaining = tuple(harness for harness in mapping.harnesses if harness not in selected)
    if len(remaining) == len(mapping.harnesses):
        statuses.append(RemovalStatus(RemovalState.SHARED_RETAINED, destination))
        retained_links.append(link)
        return
    if remaining:
        statuses.append(RemovalStatus(RemovalState.SHARED_RETAINED, destination))
        retained_links.append(OwnedLink(replace(mapping, harnesses=remaining)))
        return

    if not os.path.lexists(destination):
        statuses.append(RemovalStatus(RemovalState.MISSING_OWNED_LINK, destination))
        return
    if backend.resolved_target(destination) == mapping.source.resolve():
        statuses.append(RemovalStatus(RemovalState.OWNED, destination))
        remove_links.append(RemoveLink(link))
        removed_destinations.add(destination)
    else:
        statuses.append(RemovalStatus(RemovalState.FOREIGN_CONTENT, destination))
        retained_links.append(link)


def _classify_backups(
    backups: tuple[OwnedBackup, ...],
    home: Path,
    removed_destinations: set[Path],
    statuses: list[RemovalStatus],
) -> tuple[list[RestoreFile], list[OwnedBackup]]:
    restores: list[RestoreFile] = []
    retained: list[OwnedBackup] = []
    for backup in backups:
        if not is_path_within(backup.original, home, follow_leaf=False):
            statuses.append(RemovalStatus(RemovalState.FOREIGN_CONTENT, backup.original))
            retained.append(backup)
            continue
        if not is_path_within(backup.backup, home, follow_leaf=True):
            statuses.append(RemovalStatus(RemovalState.FOREIGN_CONTENT, backup.backup))
            retained.append(backup)
            continue
        if backup.original not in removed_destinations:
            retained.append(backup)
            continue
        if not backup.backup.exists():
            statuses.append(RemovalStatus(RemovalState.BACKUP_MISSING, backup.backup))
            retained.append(backup)
        elif file_sha256(backup.backup) != backup.sha256:
            statuses.append(RemovalStatus(RemovalState.BACKUP_MODIFIED, backup.backup))
            retained.append(backup)
        else:
            restores.append(RestoreFile(backup))
    return restores, retained


def _classify_parents(
    created_parents: tuple[Path, ...],
    home: Path,
    remove_links: list[RemoveLink],
    restores: list[RestoreFile],
    statuses: list[RemovalStatus],
) -> tuple[list[RemoveDirectory], list[Path]]:
    removals: list[RemoveDirectory] = []
    retained: list[Path] = []
    removed_names: dict[Path, set[str]] = {}
    for remove in remove_links:
        destination = remove.link.mapping.destination
        removed_names.setdefault(destination.parent, set()).add(destination.name)
    restored_names: dict[Path, set[str]] = {}
    for restore in restores:
        original = restore.backup.original
        restored_names.setdefault(original.parent, set()).add(original.name)

    for parent in created_parents:
        if not is_path_within(parent, home, follow_leaf=True):
            statuses.append(RemovalStatus(RemovalState.FOREIGN_CONTENT, parent))
            retained.append(parent)
            continue
        if not parent.exists():
            continue
        current = {entry.name for entry in parent.iterdir()}
        after = (current - removed_names.get(parent, set())) | restored_names.get(parent, set())
        if after:
            statuses.append(RemovalStatus(RemovalState.PARENT_PRESERVED, parent))
            retained.append(parent)
        else:
            removals.append(RemoveDirectory(parent))

    removals.sort(key=lambda change: (-len(change.path.parts), change.path.as_posix()))
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
