"""Errors raised while executing and rolling back an install or uninstall plan."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class BackupPathOccupied(Exception):
    """Raised before backup mutation when the planned destination is occupied."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"backup destination is already occupied: {path}")


@dataclass(frozen=True)
class RollbackFailure:
    """One compensation that could not be applied while rolling back."""

    operation: str
    path: Path
    detail: str


class ExecutionError(Exception):
    """Raised when a plan mutation fails; carries the original cause and rollback outcome.

    ``recoverable_paths`` names every managed path that rollback could not restore and a
    human must repair. When rollback fully succeeds the tuple is empty and the prior state
    was restored.
    """

    def __init__(
        self,
        original: BaseException,
        rollback_failures: tuple[RollbackFailure, ...],
        recoverable_paths: tuple[Path, ...],
    ) -> None:
        self.original = original
        self.rollback_failures = rollback_failures
        self.recoverable_paths = recoverable_paths
        if rollback_failures:
            summary = (
                f"install failed ({original!r}); rollback left "
                f"{len(recoverable_paths)} path(s) needing manual recovery: "
                f"{', '.join(str(path) for path in recoverable_paths)}"
            )
        else:
            summary = f"install failed and was rolled back cleanly ({original!r})"
        super().__init__(summary)
