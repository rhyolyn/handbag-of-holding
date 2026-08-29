"""Read-only filesystem classification and install-plan construction."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from .models import (
    ActionKind,
    Finding,
    FindingState,
    InstallPlan,
    PlannedAction,
    Projection,
    ProjectionKind,
    SkillDescriptor,
)


def build_install_plan(
    projections: tuple[Projection, ...],
    catalog: tuple[SkillDescriptor, ...],
    backup_conflicts: bool,
    timestamp: datetime,
) -> InstallPlan:
    """Classify current projection state without mutating it and plan safe actions."""
    findings: list[Finding] = []
    actions: list[PlannedAction] = []

    for projection in sorted(projections, key=lambda item: item.destination.as_posix()):
        projection_findings, projection_actions = _classify_projection(
            projection,
            tuple(sorted(catalog, key=lambda skill: skill.name)),
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

    can_backup = (
        backup_conflicts and projection.kind is ProjectionKind.GUIDANCE and destination.is_file()
    )
    finding = Finding(
        FindingState.UNRELATED,
        destination,
        projection,
        blocking=not can_backup,
    )
    if not can_backup:
        return [finding], []

    backup = destination.with_name(
        f"{destination.name}.backup-{timestamp.strftime('%Y%m%d-%H%M%S')}"
    )
    return [finding], [
        PlannedAction(ActionKind.BACKUP, destination, backup, False),
        _link_action(ActionKind.CREATE_LINK, projection.source, destination, projection),
    ]


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
    findings = [
        Finding(FindingState.COMPATIBLE_SKILL_DIRECTORY, projection.destination, projection)
    ]
    actions: list[PlannedAction] = []

    for skill in catalog:
        destination = projection.destination / skill.name
        if not os.path.lexists(destination):
            findings.append(Finding(FindingState.MISSING, destination, projection))
            actions.append(
                PlannedAction(ActionKind.CREATE_LINK, skill.directory, destination, True)
            )
        elif (
            _is_link(destination)
            and destination.exists()
            and _same_target(destination, skill.directory)
        ):
            findings.append(Finding(FindingState.CORRECT, destination, projection))
        else:
            findings.append(
                Finding(
                    FindingState.SKILL_NAME_COLLISION,
                    destination,
                    projection,
                    blocking=True,
                )
            )

    return findings, actions


def _link_action(
    kind: ActionKind, source: Path, destination: Path, projection: Projection
) -> PlannedAction:
    return PlannedAction(kind, source, destination, projection.is_directory)


def _same_target(destination: Path, source: Path) -> bool:
    return destination.resolve(strict=False) == source.resolve(strict=False)


def _is_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction is not None and is_junction())
