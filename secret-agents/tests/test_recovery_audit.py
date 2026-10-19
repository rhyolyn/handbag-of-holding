"""Consolidation evidence must remain verifiable after retiring the source checkout."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def audit_script(tmp_path: Path) -> Path:
    destination = tmp_path / "handbag-of-holding/secret-agents"
    shutil.copytree(
        ROOT,
        destination,
        ignore=shutil.ignore_patterns(
            "__pycache__", ".venv", ".mypy_cache", ".ruff_cache", ".pytest_cache", "*.egg-info"
        ),
    )
    return destination / "docs/migrations/2026-10-13-spec-recovery/verify_recovery.py"


def test_preservation_audit_uses_archives_without_requiring_old_checkout(audit_script: Path) -> None:
    result = subprocess.run([sys.executable, "-B", str(audit_script)], capture_output=True, text=True, check=False)
    data = json.loads(result.stdout)
    assert result.returncode == 0, data["errors"]
    assert data["ok"] is True
    assert data["recovery_archive_files"] == 181
    assert data["recovery_source_comparison"] == "not requested"
    assert data["unchanged_recovery_source_files"] == 0


def test_explicit_missing_original_checkout_fails(audit_script: Path, tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-B", str(audit_script), "--original-checkout", str(tmp_path / "missing")],
        capture_output=True,
        text=True,
        check=False,
    )
    data = json.loads(result.stdout)
    assert result.returncode == 1
    assert data["ok"] is False
    assert data["unchanged_recovery_source_files"] == 0
    assert any("Recovery source missing:" in error for error in data["errors"])


def test_modified_archive_still_fails_without_original_checkout(audit_script: Path) -> None:
    archive_path = audit_script.parent.parent / "2026-10-13-worky-agent/original-trees.zip"
    with ZipFile(archive_path) as archive:
        members = [(entry, archive.read(entry)) for entry in archive.infolist()]
    changed = False
    with ZipFile(archive_path, "w") as archive:
        for entry, content in members:
            if not changed and not entry.is_dir():
                content += b"\nmodified\n"
                changed = True
            archive.writestr(entry, content)
    assert changed
    result = subprocess.run([sys.executable, "-B", str(audit_script)], capture_output=True, text=True, check=False)
    data = json.loads(result.stdout)
    assert result.returncode == 1
    assert "Initial ZIP hash changed" in data["errors"]
