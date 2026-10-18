"""Immutable workspace state shared by work-tracking commands."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
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
        if require_exists and not path.exists():
            raise WorkspaceLocationError(name, path)
        return path
