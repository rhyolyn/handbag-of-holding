"""Errors raised while resolving and validating the canonical agent root."""

from pathlib import Path


class RootResolutionError(Exception):
    """Raised when the canonical agent root cannot be resolved or validated."""


class RootNotResolved(RootResolutionError):
    def __init__(self, marker_name: str) -> None:
        self.marker_name = marker_name
        super().__init__(
            "Could not resolve the canonical agent root. Pass it explicitly with --agent-root, "
            "set the SECRET_AGENTS_ROOT environment variable, or run from a checkout whose "
            f"ancestor contains a valid {marker_name} marker."
        )


class MissingRootMarker(RootResolutionError):
    def __init__(self, path: Path, marker_name: str) -> None:
        self.path = path
        self.marker_name = marker_name
        super().__init__(f"{path}: missing {marker_name} marker")


class InvalidRootMarker(RootResolutionError):
    def __init__(self, path: Path, marker_name: str, cause: Exception) -> None:
        self.path = path
        self.marker_name = marker_name
        super().__init__(f"{path}: unreadable or invalid {marker_name} ({cause})")


class RootMarkerNotObject(RootResolutionError):
    def __init__(self, path: Path, marker_name: str) -> None:
        self.path = path
        self.marker_name = marker_name
        super().__init__(f"{path}: {marker_name} must contain a JSON object")


class RootIdentityMismatch(RootResolutionError):
    def __init__(self, path: Path, required: str, actual: object) -> None:
        self.path = path
        self.required = required
        self.actual = actual
        super().__init__(f"{path}: identity must be {required!r}, found {actual!r}")


class RootSchemaVersionMismatch(RootResolutionError):
    def __init__(self, path: Path, required: int, actual: object) -> None:
        self.path = path
        self.required = required
        self.actual = actual
        super().__init__(f"{path}: schema_version must be {required}, found {actual!r}")


class MissingRootEntry(RootResolutionError):
    def __init__(self, path: Path, entry: str) -> None:
        self.path = path
        self.entry = entry
        super().__init__(f"{path}: missing required entry {entry!r}")
