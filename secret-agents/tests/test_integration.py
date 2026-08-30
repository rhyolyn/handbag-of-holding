"""End-to-end CLI integration against a temporary home and canonical root."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest

from secret_agents_setup.cli import ExitCode, main
from secret_agents_setup.link_errors import SymlinkPrivilegeRequired
from secret_agents_setup.links import LinkBackend, backend_for
from secret_agents_setup.receipts import receipt_path

CLOCK = datetime(2026, 8, 29, 12, 0, 0)
IDENTITY = "handbag-secret-agents"


class _ProbeFailBackend:
    """A backend whose capability probe refuses before any managed mutation."""

    def probe_file_link_capability(self, probe_root: Path) -> None:
        raise SymlinkPrivilegeRequired()

    def create_directory_link(self, src: Path, dst: Path) -> None:  # pragma: no cover - never reached
        raise AssertionError("probe should have blocked mutation")

    def create_file_link(self, src: Path, dst: Path) -> None:  # pragma: no cover - never reached
        raise AssertionError("probe should have blocked mutation")

    def remove_link(self, path: Path) -> None:  # pragma: no cover - never reached
        raise AssertionError("probe should have blocked mutation")

    def resolved_target(self, path: Path) -> Path:  # pragma: no cover - never reached
        return path


def _make_agent_root(tmp_path: Path) -> Path:
    root = tmp_path / "canonical"
    (root / "skills" / "alpha").mkdir(parents=True)
    (root / "skills" / "alpha" / "SKILL.md").write_text(
        "---\nname: alpha\ndescription: Alpha skill\n---\n", encoding="utf-8"
    )
    (root / "runbooks").mkdir()
    (root / "AGENTS.md").write_text("guidance", encoding="utf-8")
    (root / "model-routing.json").write_text("{}", encoding="utf-8")
    (root / ".agent-root.json").write_text(
        '{"identity": "handbag-secret-agents", "schema_version": 1}', encoding="utf-8"
    )
    return root


def _host_backend_or_skip(tmp_path: Path) -> LinkBackend:
    backend = backend_for(os.name)
    probe = tmp_path / "probe"
    probe.mkdir()
    try:
        backend.probe_file_link_capability(probe)
    except SymlinkPrivilegeRequired as exc:  # pragma: no cover - unprivileged Windows
        pytest.skip(f"host cannot create the file links this lifecycle needs: {exc}")
    return backend


def test_full_lifecycle_with_backup_and_third_party(tmp_path: Path) -> None:
    root = _make_agent_root(tmp_path)
    home = tmp_path / "home"
    skills_dir = home / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "third-party").mkdir()
    guidance = home / ".claude" / "CLAUDE.md"
    guidance.write_text("user guidance", encoding="utf-8")
    backend = _host_backend_or_skip(tmp_path)

    def run(*extra: str) -> int:
        return main(
            [*extra, "--agent-root", str(root)],
            environment={},
            home=home,
            script_path=root,
            os_name=os.name,
            now=lambda: CLOCK,
            backend=backend,
        )

    receipt_file = receipt_path(home, IDENTITY)
    backup = guidance.with_name("CLAUDE.md.backup-20260829-120000")
    alpha_link = skills_dir / "alpha"

    # dry-run mutates nothing
    assert run("install", "--harness", "claude", "--backup-conflicts", "--dry-run") == ExitCode.SUCCESS
    assert not alpha_link.exists()
    assert not backup.exists()
    assert guidance.read_text(encoding="utf-8") == "user guidance"
    assert not receipt_file.exists()

    # install: link the skill beside the third-party skill and back up the conflicting guidance
    assert run("install", "--harness", "claude", "--backup-conflicts") == ExitCode.SUCCESS
    assert alpha_link.resolve() == (root / "skills" / "alpha").resolve()
    assert (skills_dir / "third-party").is_dir()
    assert backup.read_text(encoding="utf-8") == "user guidance"
    assert guidance.resolve() == (root / "AGENTS.md").resolve()
    assert receipt_file.exists()

    # check reports the installed state as correct
    assert run("check", "--harness", "claude") == ExitCode.SUCCESS

    # a second install is idempotent and does not rewrite the receipt
    before = receipt_file.read_bytes()
    assert run("install", "--harness", "claude", "--backup-conflicts") == ExitCode.SUCCESS
    assert receipt_file.read_bytes() == before

    # uninstall removes owned links, restores the backup, and preserves the third-party skill
    assert run("uninstall", "--harness", "claude") == ExitCode.SUCCESS
    assert not alpha_link.exists()
    assert (skills_dir / "third-party").is_dir()
    assert guidance.read_text(encoding="utf-8") == "user guidance"
    assert not backup.exists()
    assert not receipt_file.exists()
    assert receipt_file.parent.exists()  # receipt-storage directory is retained
    assert (root / "skills" / "alpha").is_dir()  # canonical target intact


def test_windows_capability_failure_makes_zero_changes(tmp_path: Path) -> None:
    root = _make_agent_root(tmp_path)
    home = tmp_path / "home"
    home.mkdir()

    code = main(
        ["install", "--harness", "codex", "--agent-root", str(root)],
        environment={},
        home=home,
        script_path=root,
        os_name="nt",
        now=lambda: CLOCK,
        backend=_ProbeFailBackend(),
    )

    assert code == ExitCode.BLOCKED
    assert not (home / ".agents").exists()
    assert not (home / ".codex").exists()
    assert not receipt_path(home, IDENTITY).exists()


def test_backend_for_current_host_completes_or_refuses(tmp_path: Path) -> None:
    root = _make_agent_root(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    backend = backend_for(os.name)

    def install() -> int:
        return main(
            ["install", "--harness", "codex", "--agent-root", str(root)],
            environment={},
            home=home,
            script_path=root,
            os_name=os.name,
            now=lambda: CLOCK,
            backend=backend,
        )

    probe = tmp_path / "probe"
    probe.mkdir()
    try:
        backend.probe_file_link_capability(probe)
    except SymlinkPrivilegeRequired:  # pragma: no cover - unprivileged Windows
        assert install() == ExitCode.BLOCKED
        assert not (home / ".agents").exists()
        assert not receipt_path(home, IDENTITY).exists()
        return

    assert install() == ExitCode.SUCCESS
    assert (home / ".agents" / "skills").resolve() == (root / "skills").resolve()
    assert receipt_path(home, IDENTITY).exists()
