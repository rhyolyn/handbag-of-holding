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
