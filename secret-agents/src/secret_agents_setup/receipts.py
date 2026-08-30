"""Atomic install-receipt persistence and ownership validation."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .models import (
    Harness,
    InstallReceipt,
    ProjectionKind,
    ReceiptBackup,
    ReceiptProjection,
)
from .path_safety import is_path_within
from .receipt_errors import (
    DuplicateReceiptDestination,
    MalformedReceipt,
    NonAbsoluteReceiptPath,
    ReceiptIdentityMismatch,
    ReceiptPathOutsideHome,
    ReceiptSourceOutsideRoot,
    UnsupportedReceiptSchema,
)
from .receipt_errors import ReceiptError as ReceiptError

RECEIPT_SCHEMA_VERSION = 1
_RECEIPT_STORE = ".secret-agents"
_INSTALLATIONS = "installations"


def receipt_path(home: Path, identity: str) -> Path:
    """Return the canonical receipt path for a root identity under a managed home."""
    return home / _RECEIPT_STORE / _INSTALLATIONS / f"{identity}-v{RECEIPT_SCHEMA_VERSION}.json"


def file_sha256(path: Path) -> str:
    """Return the hex SHA-256 digest of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_receipt_atomic(receipt: InstallReceipt, path: Path) -> None:
    """Serialize a receipt deterministically and replace the target atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(_to_document(receipt), indent=2, ensure_ascii=False)
    tmp = path.with_name(f"{path.name}.tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def load_receipt(path: Path, *, expected_identity: str, home: Path) -> InstallReceipt | None:
    """Load and validate a receipt, or return ``None`` when no receipt exists."""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise MalformedReceipt(path, str(exc)) from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MalformedReceipt(path, f"invalid JSON ({exc})") from exc

    return _from_document(data, path=path, expected_identity=expected_identity, home=home)


def _to_document(receipt: InstallReceipt) -> dict[str, object]:
    return {
        "schema_version": receipt.schema_version,
        "root_identity": receipt.root_identity,
        "installed_root": str(receipt.installed_root),
        "projections": [
            {
                "destination": str(projection.destination),
                "source": str(projection.source),
                "kind": projection.kind.value,
                "harnesses": [harness.value for harness in projection.harnesses],
            }
            for projection in receipt.projections
        ],
        "backups": [
            {
                "original": str(backup.original),
                "backup": str(backup.backup),
                "sha256": backup.sha256,
            }
            for backup in receipt.backups
        ],
        "created_parents": [str(parent) for parent in receipt.created_parents],
    }


def _from_document(
    data: object,
    *,
    path: Path,
    expected_identity: str,
    home: Path,
) -> InstallReceipt:
    document = _require_object(data, path, "<root>")

    schema_version = document.get("schema_version")
    if schema_version != RECEIPT_SCHEMA_VERSION:
        raise UnsupportedReceiptSchema(path, schema_version, RECEIPT_SCHEMA_VERSION)

    identity = document.get("root_identity")
    if identity != expected_identity:
        raise ReceiptIdentityMismatch(path, expected_identity, identity)

    installed_root = _abs_path(document.get("installed_root"), path, "installed_root")
    projections = _load_projections(document.get("projections"), path, home, installed_root)
    backups = _load_backups(document.get("backups"), path, home)
    created_parents = _load_created_parents(document.get("created_parents"), path, home)

    return InstallReceipt(
        schema_version=RECEIPT_SCHEMA_VERSION,
        root_identity=identity,
        installed_root=installed_root,
        projections=projections,
        backups=backups,
        created_parents=created_parents,
    )


def _load_projections(value: object, path: Path, home: Path, installed_root: Path) -> tuple[ReceiptProjection, ...]:
    entries = _require_list(value, path, "projections")
    projections: list[ReceiptProjection] = []
    seen: set[Path] = set()
    for entry in entries:
        mapping = _require_object(entry, path, "projections[]")
        destination = _abs_path(mapping.get("destination"), path, "destination")
        _require_within_home(destination, path, "destination", home, follow_leaf=False)
        if destination in seen:
            raise DuplicateReceiptDestination(path, destination)
        seen.add(destination)
        source = _abs_path(mapping.get("source"), path, "source")
        if not is_path_within(source, installed_root, follow_leaf=True):
            raise ReceiptSourceOutsideRoot(path, source, installed_root)
        projections.append(
            ReceiptProjection(
                destination=destination,
                source=source,
                kind=_require_kind(mapping.get("kind"), path),
                harnesses=_require_harnesses(mapping.get("harnesses"), path),
            )
        )
    return tuple(projections)


def _load_backups(value: object, path: Path, home: Path) -> tuple[ReceiptBackup, ...]:
    entries = _require_list(value, path, "backups")
    backups: list[ReceiptBackup] = []
    for entry in entries:
        mapping = _require_object(entry, path, "backups[]")
        original = _abs_path(mapping.get("original"), path, "original")
        _require_within_home(original, path, "original", home, follow_leaf=False)
        backup = _abs_path(mapping.get("backup"), path, "backup")
        _require_within_home(backup, path, "backup", home, follow_leaf=True)
        sha256 = mapping.get("sha256")
        if not isinstance(sha256, str):
            raise MalformedReceipt(path, "backup sha256 must be a string")
        backups.append(ReceiptBackup(original=original, backup=backup, sha256=sha256))
    return tuple(backups)


def _load_created_parents(value: object, path: Path, home: Path) -> tuple[Path, ...]:
    entries = _require_list(value, path, "created_parents")
    parents: list[Path] = []
    for entry in entries:
        parent = _abs_path(entry, path, "created_parents")
        _require_within_home(parent, path, "created_parents", home, follow_leaf=True)
        parents.append(parent)
    return tuple(parents)


def _require_object(value: object, path: Path, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise MalformedReceipt(path, f"{field} must be an object")
    return value


def _require_list(value: object, path: Path, field: str) -> list[object]:
    if not isinstance(value, list):
        raise MalformedReceipt(path, f"{field} must be a list")
    return value


def _abs_path(value: object, path: Path, field: str) -> Path:
    if not isinstance(value, str):
        raise MalformedReceipt(path, f"{field} must be a string")
    candidate = Path(value)
    if not candidate.is_absolute():
        raise NonAbsoluteReceiptPath(path, field, value)
    return candidate


def _require_within_home(value: Path, path: Path, field: str, home: Path, *, follow_leaf: bool) -> None:
    if not is_path_within(value, home, follow_leaf=follow_leaf):
        raise ReceiptPathOutsideHome(path, field, value, home)


def _require_kind(value: object, path: Path) -> ProjectionKind:
    if not isinstance(value, str):
        raise MalformedReceipt(path, f"projection kind {value!r} must be a string")
    try:
        return ProjectionKind(value)
    except ValueError as exc:
        raise MalformedReceipt(path, f"invalid projection kind {value!r}") from exc


def _require_harnesses(value: object, path: Path) -> tuple[Harness, ...]:
    entries = _require_list(value, path, "harnesses")
    harnesses: list[Harness] = []
    for entry in entries:
        if not isinstance(entry, str):
            raise MalformedReceipt(path, f"harness value {entry!r} must be a string")
        try:
            harnesses.append(Harness(entry))
        except ValueError as exc:
            raise MalformedReceipt(path, f"invalid harness value ({exc})") from exc
    return tuple(harnesses)
