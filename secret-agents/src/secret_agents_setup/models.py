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
