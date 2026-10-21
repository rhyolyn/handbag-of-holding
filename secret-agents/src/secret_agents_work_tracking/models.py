"""Immutable workspace state shared by work-tracking commands."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Literal
from zoneinfo import ZoneInfo

from .errors import WorkspaceLocationError

LocationName = Literal[
    "receipts",
    "daily_notes",
    "perforce_checkins",
    "git_checkins",
    "status_reports",
    "monthly_reports",
    "annual_reviews",
    "templates",
    "imports",
    "ledgers",
]


@dataclass(frozen=True)
class Workspace:
    """Own the validated paths and timezone for one work-tracking invocation."""

    config_path: Path
    vault_root: Path
    tracking_root: Path
    timezone: ZoneInfo
    locations: Mapping[LocationName, Path]

    def __post_init__(self) -> None:
        object.__setattr__(self, "locations", MappingProxyType(dict(self.locations)))

    def location(self, name: LocationName, *, require_exists: bool) -> Path:
        """Return one named location and reject a missing required input."""
        path = self.locations[name]
        if require_exists and not path.is_dir():
            raise WorkspaceLocationError(name, path)
        return path


class OutputDecision(StrEnum):
    """Describe whether an evidence-derived output can be written safely."""

    CREATE = "create"
    SKIP_IDENTICAL = "skip-identical"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class EvidenceRecord:
    """One validated evidence artifact with its durable provenance."""

    kind: str
    occurred_start: date
    occurred_end: date
    source_system: str
    source_id: str
    initiatives: tuple[str, ...]
    tags: tuple[str, ...]
    status: str
    sources: tuple[str, ...]
    source_path: Path
    body: str
    normalized_content: str
    pr_commit_urls: frozenset[str]


@dataclass(frozen=True)
class EvidenceDiagnostic:
    """Explain why one evidence file was excluded without hiding its path."""

    path: Path
    reason: str


@dataclass(frozen=True)
class EvidenceSelection:
    """Retain the evidence records and diagnostics selected for a window."""

    records: tuple[EvidenceRecord, ...]
    diagnostics: tuple[EvidenceDiagnostic, ...]


@dataclass(frozen=True)
class ReportingWindow:
    """Represent a Pacific reporting period with an exclusive end date."""

    start: date
    end_exclusive: date


@dataclass(frozen=True)
class YearMonth:
    """Identify one calendar month for report routing."""

    year: int
    month: int


@dataclass(frozen=True)
class MigrationEntry:
    """Describe one classified legacy artifact without moving it."""

    source: Path
    destination: Path
    classification: str
    rationale: str
    content_hash: str
    semantic_hash: str


@dataclass(frozen=True)
class MigrationInventory:
    """Own the read-only classification result for one legacy vault."""

    workspace: Workspace
    classified: tuple[MigrationEntry, ...]
    untouched: tuple[Path, ...]


@dataclass(frozen=True)
class MigrationPlan:
    """Represent a preflight-approved, still-unapplied migration."""

    inventory: MigrationInventory


@dataclass(frozen=True)
class MigrationMove:
    """Record one completed migration output and its preserved hashes."""

    source: Path
    destination: Path
    content_hash: str
    output_hash: str
    rewritten_links: tuple[str, ...]


@dataclass(frozen=True)
class MigrationAudit:
    """Report completed, unresolved, and intentionally untouched migration work."""

    moved: tuple[MigrationMove, ...]
    unresolved: tuple[str, ...]
    untouched: tuple[Path, ...]


@dataclass(frozen=True)
class ReportInput:
    """Represent one immutable, source-provenanced report generation input."""

    kind: str
    window: ReportingWindow
    output_path: Path
    sources: tuple[Path, ...]
    source_links: tuple[str, ...]
    diagnostics: tuple[EvidenceDiagnostic, ...]
    incomplete: bool
    decision: OutputDecision
