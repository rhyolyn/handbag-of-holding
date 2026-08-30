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
