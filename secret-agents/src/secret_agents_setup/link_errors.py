"""Errors raised by cross-platform link operations."""

from pathlib import Path
from subprocess import CompletedProcess


class LinkOperationError(Exception):
    """Raised when a link operation cannot be completed safely."""


class JunctionFailed(LinkOperationError):
    def __init__(self, src: Path, dst: Path, result: CompletedProcess[str]) -> None:
        super().__init__(
            f"junction command failed for src {src} and dst {dst}; stdout: {result.stdout!r}; stderr: {result.stderr!r}"
        )


class SymlinkFailed(LinkOperationError):
    def __init__(self, src: Path, dst: Path, exc: OSError) -> None:
        super().__init__(f"file symbolic link failed for src {src} and dst {dst}: {exc}")


class LinkTargetMismatch(LinkOperationError):
    def __init__(self, dst: Path, resolved_dst: Path, resolved_src: Path) -> None:
        super().__init__(f"created link dst {dst} resolved to {resolved_dst}, not src {resolved_src}")


class PartialLinkCleanupFailed(LinkOperationError):
    """Raised when a failed link creation leaves a path requiring manual recovery."""

    def __init__(self, destination: Path, create_error: BaseException, cleanup_error: Exception) -> None:
        self.destination = destination
        self.create_error = create_error
        self.cleanup_error = cleanup_error
        self.recoverable_path = destination
        super().__init__(f"failed to clean partial link at {destination}: {cleanup_error}")


class NotALink(LinkOperationError):
    def __init__(self, path: Path) -> None:
        super().__init__(f"refuse to remove non-link path: {path}")


class SymlinkPrivilegeRequired(LinkOperationError):
    WINERROR_PRIVILEGE_NOT_HELD = 1314
    MESSAGE = (
        f"Windows file symbolic links require Developer Mode or elevation (winerror {WINERROR_PRIVILEGE_NOT_HELD})."
    )

    def __init__(self) -> None:
        super().__init__(self.MESSAGE)


class SymlinkUnsupported(LinkOperationError):
    def __init__(self, exc: OSError) -> None:
        super().__init__(f"Windows file symbolic-link capability probe failed: {exc}")
