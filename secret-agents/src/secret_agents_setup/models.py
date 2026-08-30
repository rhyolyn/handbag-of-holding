"""Frozen models shared across discovery, planning, and execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .receipts import InstallReceipt


class Harness(StrEnum):
    CODEX = "codex"
    CLAUDE = "claude"
    COPILOT = "copilot"
    ALL = "all"


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
class ExecutionEvent:
    kind: ExecutionEventKind
    path: Path


@dataclass(frozen=True)
class ExecutionReport:
    events: tuple[ExecutionEvent, ...]
    receipt: InstallReceipt | None
    receipt_written: bool


class UninstallFindingState(StrEnum):
    NOT_INSTALLED = "not-installed"
    OWNED = "owned"
    MISSING_OWNED_LINK = "missing-owned-link"
    SHARED_RETAINED = "shared-retained"
    FOREIGN_CONTENT = "foreign-content"
    BACKUP_MISSING = "backup-missing"
    BACKUP_MODIFIED = "backup-modified"
    PARENT_PRESERVED = "parent-preserved"


class UninstallActionKind(StrEnum):
    REMOVE_LINK = "remove-link"
    RESTORE_BACKUP = "restore-backup"
    REMOVE_EMPTY_PARENT = "remove-empty-parent"
    REPLACE_RECEIPT = "replace-receipt"
    DELETE_RECEIPT = "delete-receipt"


@dataclass(frozen=True)
class UninstallFinding:
    state: UninstallFindingState
    path: Path
    blocking: bool = False


@dataclass(frozen=True)
class UninstallAction:
    kind: UninstallActionKind
    source: Path | None
    destination: Path


@dataclass(frozen=True)
class UninstallPlan:
    findings: tuple[UninstallFinding, ...]
    actions: tuple[UninstallAction, ...]
    next_receipt: InstallReceipt | None

    @property
    def can_apply(self) -> bool:
        return not any(finding.blocking for finding in self.findings)
