"""Atomic install-receipt persistence and ownership validation.

Receipts own the record of what an install created: each ``OwnedLink`` wraps the
concrete ``InstallMapping`` it installed, and each ``OwnedBackup`` records a
displaced user file. Serialization stays on schema version 1: the JSON keeps the
``"projections"`` array and its ``"kind": "guidance" | "skills"`` discriminator,
which deserialize back into ``InstructionsMapping`` and ``SkillsMapping``.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .harness_profiles import InstallMapping, InstructionsMapping, SkillsMapping
from .models import Harness
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


@dataclass(frozen=True)
class OwnedLink:
    """A link an install created, identified by the mapping it installed."""

    mapping: InstallMapping


@dataclass(frozen=True)
class OwnedBackup:
    """A user file an install displaced, with the digest proving it unchanged."""

    original: Path
    backup: Path
    sha256: str


@dataclass(frozen=True)
class InstallReceipt:
    schema_version: int
    root_identity: str
    installed_root: Path
    links: tuple[OwnedLink, ...]
    backups: tuple[OwnedBackup, ...]
    created_parents: tuple[Path, ...]


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


def _kind_for(mapping: InstallMapping) -> str:
    return "skills" if isinstance(mapping, SkillsMapping) else "guidance"


def _to_document(receipt: InstallReceipt) -> dict[str, object]:
    return {
        "schema_version": receipt.schema_version,
        "root_identity": receipt.root_identity,
        "installed_root": str(receipt.installed_root),
        "projections": [
            {
                "destination": str(link.mapping.destination),
                "source": str(link.mapping.source),
                "kind": _kind_for(link.mapping),
                "harnesses": [harness.value for harness in link.mapping.harnesses],
            }
            for link in receipt.links
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
    links = _load_links(document.get("projections"), path, home, installed_root)
    backups = _load_backups(document.get("backups"), path, home)
    created_parents = _load_created_parents(document.get("created_parents"), path, home)

    return InstallReceipt(
        schema_version=RECEIPT_SCHEMA_VERSION,
        root_identity=identity,
        installed_root=installed_root,
        links=links,
        backups=backups,
        created_parents=created_parents,
    )


def _load_links(value: object, path: Path, home: Path, installed_root: Path) -> tuple[OwnedLink, ...]:
    entries = _require_list(value, path, "projections")
    links: list[OwnedLink] = []
    seen: set[Path] = set()
    for entry in entries:
        document = _require_object(entry, path, "projections[]")
        destination = _abs_path(document.get("destination"), path, "destination")
        _require_within_home(destination, path, "destination", home, follow_leaf=False)
        if destination in seen:
            raise DuplicateReceiptDestination(path, destination)
        seen.add(destination)
        source = _abs_path(document.get("source"), path, "source")
        if not is_path_within(source, installed_root, follow_leaf=True):
            raise ReceiptSourceOutsideRoot(path, source, installed_root)
        harnesses = _require_harnesses(document.get("harnesses"), path)
        mapping = _mapping_from_document(document.get("kind"), harnesses, source, destination, path)
        links.append(OwnedLink(mapping))
    return tuple(links)


def _mapping_from_document(
    kind: object,
    harnesses: tuple[Harness, ...],
    source: Path,
    destination: Path,
    path: Path,
) -> InstallMapping:
    if not isinstance(kind, str):
        raise MalformedReceipt(path, f"projection kind {kind!r} must be a string")
    if kind == "skills":
        return SkillsMapping(harnesses=harnesses, source=source, destination=destination)
    if kind == "guidance":
        return InstructionsMapping(harnesses=harnesses, source=source, destination=destination)
    raise MalformedReceipt(path, f"invalid projection kind {kind!r}")


def _load_backups(value: object, path: Path, home: Path) -> tuple[OwnedBackup, ...]:
    entries = _require_list(value, path, "backups")
    backups: list[OwnedBackup] = []
    for entry in entries:
        document = _require_object(entry, path, "backups[]")
        original = _abs_path(document.get("original"), path, "original")
        _require_within_home(original, path, "original", home, follow_leaf=False)
        backup = _abs_path(document.get("backup"), path, "backup")
        _require_within_home(backup, path, "backup", home, follow_leaf=True)
        sha256 = document.get("sha256")
        if not isinstance(sha256, str):
            raise MalformedReceipt(path, "backup sha256 must be a string")
        backups.append(OwnedBackup(original=original, backup=backup, sha256=sha256))
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
