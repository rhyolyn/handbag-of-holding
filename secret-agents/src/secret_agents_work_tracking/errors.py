"""Actionable errors raised by the work-tracking workspace boundary."""

from __future__ import annotations

from pathlib import Path


class WorkspaceError(Exception):
    """Base class for failures a user can resolve in workspace configuration."""


class WorkspaceConfigurationError(WorkspaceError):
    """Report a selected configuration that cannot define a safe workspace."""

    def __init__(self, config_path: Path, reason: str) -> None:
        super().__init__(f"{config_path}: {reason}. Fix work-tracking.yaml and run the command again.")


class WorkspaceLocationError(WorkspaceError):
    """Report a required named input location that is unavailable."""

    def __init__(self, name: str, path: Path) -> None:
        super().__init__(f"{path}: required {name} location must be an existing directory. Create it, then run again.")


class MigrationPreflightError(WorkspaceError):
    """Report a migration hazard before it can cause a partial write."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Migration preflight failed: {reason}. Resolve the source data, then run the dry-run again.")
