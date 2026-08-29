"""Frozen models shared across discovery, planning, and execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Harness(StrEnum):
    CODEX = "codex"
    CLAUDE = "claude"
    COPILOT = "copilot"
    ALL = "all"


class ProjectionKind(StrEnum):
    SKILLS = "skills"
    GUIDANCE = "guidance"


class FindingState(StrEnum):
    CORRECT = "correct"
    MISSING = "missing"
    STALE_LINK = "stale-link"
    BROKEN_LINK = "broken-link"
    UNRELATED = "unrelated"
    COMPATIBLE_SKILL_DIRECTORY = "compatible-skill-directory"
    SKILL_NAME_COLLISION = "skill-name-collision"


class ActionKind(StrEnum):
    CREATE_LINK = "create-link"
    REPLACE_LINK = "replace-link"
    BACKUP = "backup"


class ExecutionEventKind(StrEnum):
    PROBED_CAPABILITY = "probed-capability"
    CREATED_PARENT = "created-parent"
    REMOVED_STALE_LINK = "removed-stale-link"
    BACKED_UP = "backed-up"
    CREATED_LINK = "created-link"
    WROTE_RECEIPT = "wrote-receipt"
    REMOVED_LINK = "removed-link"
    RESTORED_BACKUP = "restored-backup"
    REMOVED_EMPTY_PARENT = "removed-empty-parent"
    DELETED_RECEIPT = "deleted-receipt"


@dataclass(frozen=True)
class AgentRoot:
    path: Path
    schema_version: int
    identity: str


@dataclass(frozen=True)
class SkillDescriptor:
    name: str
    description: str
    directory: Path


@dataclass(frozen=True)
class Projection:
    harnesses: tuple[Harness, ...]
    kind: ProjectionKind
    source: Path
    destination: Path
    is_directory: bool


@dataclass(frozen=True)
class Finding:
    state: FindingState
    path: Path
    projection: Projection
    blocking: bool = False


@dataclass(frozen=True)
class PlannedAction:
    kind: ActionKind
    source: Path
    destination: Path
    is_directory: bool


@dataclass(frozen=True)
class InstallPlan:
    findings: tuple[Finding, ...]
    actions: tuple[PlannedAction, ...]

    @property
    def can_apply(self) -> bool:
        return not any(finding.blocking for finding in self.findings)


@dataclass(frozen=True)
class ReceiptProjection:
    destination: Path
    source: Path
    kind: ProjectionKind
    harnesses: tuple[Harness, ...]


@dataclass(frozen=True)
class ReceiptBackup:
    original: Path
    backup: Path
    sha256: str


@dataclass(frozen=True)
class InstallReceipt:
    schema_version: int
    root_identity: str
    installed_root: Path
    projections: tuple[ReceiptProjection, ...]
    backups: tuple[ReceiptBackup, ...]
    created_parents: tuple[Path, ...]


@dataclass(frozen=True)
class ExecutionEvent:
    kind: ExecutionEventKind
    path: Path


@dataclass(frozen=True)
class ExecutionReport:
    events: tuple[ExecutionEvent, ...]
    receipt: InstallReceipt | None
    receipt_written: bool
