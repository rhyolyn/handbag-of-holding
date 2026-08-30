"""Tests for atomic install-receipt persistence and ownership validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from secret_agents_setup.harness_profiles import InstructionsMapping, SkillsMapping
from secret_agents_setup.models import Harness
from secret_agents_setup.receipt_errors import (
    DuplicateReceiptDestination,
    MalformedReceipt,
    NonAbsoluteReceiptPath,
    ReceiptError,
    ReceiptIdentityMismatch,
    ReceiptPathOutsideHome,
    ReceiptSourceOutsideRoot,
    UnsupportedReceiptSchema,
)
from secret_agents_setup.receipts import (
    InstallReceipt,
    OwnedBackup,
    OwnedLink,
    load_receipt,
    receipt_path,
    write_receipt_atomic,
)

IDENTITY = "handbag-secret-agents"


def _home_and_root(tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "home"
    root = tmp_path / "canonical"
    home.mkdir()
    root.mkdir()
    return home, root


def _receipt(home: Path, root: Path, *, identity: str = IDENTITY) -> InstallReceipt:
    return InstallReceipt(
        schema_version=1,
        root_identity=identity,
        installed_root=root,
        links=(
            OwnedLink(
                SkillsMapping(
                    harnesses=(Harness.CODEX, Harness.COPILOT),
                    source=root / "skills",
                    destination=home / ".agents" / "skills",
                )
            ),
            OwnedLink(
                InstructionsMapping(
                    harnesses=(Harness.CODEX,),
                    source=root / "AGENTS.md",
                    destination=home / ".codex" / "AGENTS.md",
                )
            ),
        ),
        backups=(
            OwnedBackup(
                original=home / ".codex" / "AGENTS.md",
                backup=home / ".codex" / "AGENTS.md.backup-20260829-120000",
                sha256="a" * 64,
            ),
        ),
        created_parents=(home / ".agents",),
    )


def _write_raw(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _serialized(receipt: InstallReceipt, path: Path) -> dict[str, object]:
    write_receipt_atomic(receipt, path)
    data: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return data


def test_receipt_path_matches_identity_and_version(tmp_path: Path) -> None:
    home = tmp_path / "home"
    assert receipt_path(home, IDENTITY) == (home / ".secret-agents" / "installations" / "handbag-secret-agents-v1.json")


def test_missing_receipt_returns_none(tmp_path: Path) -> None:
    home, _ = _home_and_root(tmp_path)
    assert load_receipt(tmp_path / "nope.json", expected_identity=IDENTITY, home=home) is None


def test_round_trip_is_deterministic(tmp_path: Path) -> None:
    home, root = _home_and_root(tmp_path)
    path = receipt_path(home, IDENTITY)
    receipt = _receipt(home, root)

    write_receipt_atomic(receipt, path)
    first = path.read_bytes()
    write_receipt_atomic(receipt, path)
    second = path.read_bytes()

    assert first == second
    loaded = load_receipt(path, expected_identity=IDENTITY, home=home)
    assert loaded == receipt


def test_schema_v1_document_loads_into_owned_links(tmp_path: Path) -> None:
    home, root = _home_and_root(tmp_path)
    path = receipt_path(home, IDENTITY)
    instructions_destination = home / ".codex" / "AGENTS.md"
    instructions_source = root / "AGENTS.md"
    skills_destination = home / ".agents" / "skills"
    skills_source = root / "skills"
    document = {
        "schema_version": 1,
        "root_identity": IDENTITY,
        "installed_root": str(root),
        "projections": [
            {
                "destination": str(instructions_destination),
                "source": str(instructions_source),
                "kind": "guidance",
                "harnesses": ["codex"],
            },
            {
                "destination": str(skills_destination),
                "source": str(skills_source),
                "kind": "skills",
                "harnesses": ["codex"],
            },
        ],
        "backups": [],
        "created_parents": [],
    }
    _write_raw(path, document)

    receipt = load_receipt(path, expected_identity=IDENTITY, home=home)

    assert receipt is not None
    assert receipt.links == (
        OwnedLink(InstructionsMapping((Harness.CODEX,), instructions_source, instructions_destination)),
        OwnedLink(SkillsMapping((Harness.CODEX,), skills_source, skills_destination)),
    )

    write_receipt_atomic(receipt, path)
    written: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    assert "projections" in written
    projections = written["projections"]
    assert isinstance(projections, list)
    assert {entry["kind"] for entry in projections} == {"guidance", "skills"}


def test_unknown_schema_version_is_rejected(tmp_path: Path) -> None:
    home, root = _home_and_root(tmp_path)
    path = receipt_path(home, IDENTITY)
    payload = _serialized(_receipt(home, root), path)
    payload["schema_version"] = 2
    _write_raw(path, payload)

    with pytest.raises(UnsupportedReceiptSchema):
        load_receipt(path, expected_identity=IDENTITY, home=home)


def test_malformed_json_is_rejected(tmp_path: Path) -> None:
    home, _ = _home_and_root(tmp_path)
    path = receipt_path(home, IDENTITY)
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(MalformedReceipt):
        load_receipt(path, expected_identity=IDENTITY, home=home)


def test_wrong_field_types_are_rejected(tmp_path: Path) -> None:
    home, root = _home_and_root(tmp_path)
    path = receipt_path(home, IDENTITY)
    payload = _serialized(_receipt(home, root), path)
    payload["projections"] = "not-a-list"
    _write_raw(path, payload)

    with pytest.raises(MalformedReceipt):
        load_receipt(path, expected_identity=IDENTITY, home=home)


def test_duplicate_projection_destinations_are_rejected(tmp_path: Path) -> None:
    home, root = _home_and_root(tmp_path)
    path = receipt_path(home, IDENTITY)
    payload = _serialized(_receipt(home, root), path)
    projections = payload["projections"]
    assert isinstance(projections, list)
    projections[1]["destination"] = projections[0]["destination"]
    _write_raw(path, payload)

    with pytest.raises(DuplicateReceiptDestination):
        load_receipt(path, expected_identity=IDENTITY, home=home)


def test_foreign_root_identity_is_rejected(tmp_path: Path) -> None:
    home, root = _home_and_root(tmp_path)
    path = receipt_path(home, IDENTITY)
    write_receipt_atomic(_receipt(home, root, identity="someone-else"), path)

    with pytest.raises(ReceiptIdentityMismatch):
        load_receipt(path, expected_identity=IDENTITY, home=home)


def test_non_absolute_paths_are_rejected(tmp_path: Path) -> None:
    home, root = _home_and_root(tmp_path)
    path = receipt_path(home, IDENTITY)
    payload = _serialized(_receipt(home, root), path)
    payload["created_parents"] = ["relative/parent"]
    _write_raw(path, payload)

    with pytest.raises(NonAbsoluteReceiptPath):
        load_receipt(path, expected_identity=IDENTITY, home=home)


def test_destination_outside_home_is_rejected(tmp_path: Path) -> None:
    home, root = _home_and_root(tmp_path)
    path = receipt_path(home, IDENTITY)
    payload = _serialized(_receipt(home, root), path)
    projections = payload["projections"]
    assert isinstance(projections, list)
    projections[0]["destination"] = str(tmp_path / "elsewhere" / "skills")
    _write_raw(path, payload)

    with pytest.raises(ReceiptPathOutsideHome):
        load_receipt(path, expected_identity=IDENTITY, home=home)


def test_destination_with_parent_traversal_is_rejected(tmp_path: Path) -> None:
    home, root = _home_and_root(tmp_path)
    path = receipt_path(home, IDENTITY)
    payload = _serialized(_receipt(home, root), path)
    projections = payload["projections"]
    assert isinstance(projections, list)
    projections[0]["destination"] = str(home / ".." / "victim")
    _write_raw(path, payload)

    with pytest.raises(ReceiptPathOutsideHome):
        load_receipt(path, expected_identity=IDENTITY, home=home)


def test_backup_path_outside_home_is_rejected(tmp_path: Path) -> None:
    home, root = _home_and_root(tmp_path)
    path = receipt_path(home, IDENTITY)
    payload = _serialized(_receipt(home, root), path)
    backups = payload["backups"]
    assert isinstance(backups, list)
    backups[0]["backup"] = str(tmp_path / "elsewhere" / "AGENTS.md.bak")
    _write_raw(path, payload)

    with pytest.raises(ReceiptPathOutsideHome):
        load_receipt(path, expected_identity=IDENTITY, home=home)


def test_created_parent_outside_home_is_rejected(tmp_path: Path) -> None:
    home, root = _home_and_root(tmp_path)
    path = receipt_path(home, IDENTITY)
    payload = _serialized(_receipt(home, root), path)
    payload["created_parents"] = [str(tmp_path / "elsewhere")]
    _write_raw(path, payload)

    with pytest.raises(ReceiptPathOutsideHome):
        load_receipt(path, expected_identity=IDENTITY, home=home)


def test_projection_source_outside_root_is_rejected(tmp_path: Path) -> None:
    home, root = _home_and_root(tmp_path)
    path = receipt_path(home, IDENTITY)
    payload = _serialized(_receipt(home, root), path)
    projections = payload["projections"]
    assert isinstance(projections, list)
    projections[0]["source"] = str(tmp_path / "other-root" / "skills")
    _write_raw(path, payload)

    with pytest.raises(ReceiptSourceOutsideRoot):
        load_receipt(path, expected_identity=IDENTITY, home=home)


def test_projection_source_with_parent_traversal_is_rejected(tmp_path: Path) -> None:
    home, root = _home_and_root(tmp_path)
    path = receipt_path(home, IDENTITY)
    payload = _serialized(_receipt(home, root), path)
    projections = payload["projections"]
    assert isinstance(projections, list)
    projections[0]["source"] = str(root / ".." / "foreign")
    _write_raw(path, payload)

    with pytest.raises(ReceiptSourceOutsideRoot):
        load_receipt(path, expected_identity=IDENTITY, home=home)


def test_atomic_write_leaves_no_temporary_file(tmp_path: Path) -> None:
    home, root = _home_and_root(tmp_path)
    path = receipt_path(home, IDENTITY)

    write_receipt_atomic(_receipt(home, root), path)

    assert [entry.name for entry in path.parent.iterdir()] == [path.name]


def test_receipt_error_family_is_shallow() -> None:
    for error in (
        MalformedReceipt,
        UnsupportedReceiptSchema,
        ReceiptIdentityMismatch,
        DuplicateReceiptDestination,
        ReceiptPathOutsideHome,
        ReceiptSourceOutsideRoot,
        NonAbsoluteReceiptPath,
    ):
        assert issubclass(error, ReceiptError)
