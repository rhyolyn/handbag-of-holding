"""Frozen models shared across discovery, planning, and execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
