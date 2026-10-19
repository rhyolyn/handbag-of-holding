"""Errors raised while loading and validating a persisted install receipt."""

from pathlib import Path


class ReceiptError(Exception):
    """Raised when a persisted receipt is invalid, unsupported, or unreadable."""


class MalformedReceipt(ReceiptError):
    def __init__(self, path: Path, detail: str) -> None:
        self.path = path
        super().__init__(f"{path}: malformed receipt ({detail})")


class UnsupportedReceiptSchema(ReceiptError):
    def __init__(self, path: Path, found: object, supported: int) -> None:
        self.path = path
        self.found = found
        super().__init__(f"{path}: unsupported receipt schema_version {found!r}, expected {supported}")


class ReceiptIdentityMismatch(ReceiptError):
    def __init__(self, path: Path, expected: str, found: object) -> None:
        self.path = path
        self.expected = expected
        self.found = found
        super().__init__(f"{path}: receipt identity {found!r} does not match expected {expected!r}")


class DuplicateReceiptDestination(ReceiptError):
    def __init__(self, path: Path, destination: Path) -> None:
        self.path = path
        self.destination = destination
        super().__init__(f"{path}: duplicate projection destination {destination}")


class NonAbsoluteReceiptPath(ReceiptError):
    def __init__(self, path: Path, field: str, value: str) -> None:
        self.path = path
        self.field = field
        self.value = value
        super().__init__(f"{path}: {field} path {value!r} is not absolute")


class ReceiptPathOutsideHome(ReceiptError):
    def __init__(self, path: Path, field: str, value: Path, home: Path) -> None:
        self.path = path
        self.field = field
        self.value = value
        self.home = home
        super().__init__(f"{path}: {field} {value} is outside managed home {home}")


class ReceiptSourceOutsideRoot(ReceiptError):
    def __init__(self, path: Path, value: Path, installed_root: Path) -> None:
        self.path = path
        self.value = value
        self.installed_root = installed_root
        super().__init__(f"{path}: projection source {value} is outside installed root {installed_root}")
