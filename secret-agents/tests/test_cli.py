"""Tests for the install/check/uninstall CLI orchestration and exit codes."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest

import secret_agents_setup.cli as cli_module
from secret_agents_setup.cli import ExitCode, main
from secret_agents_setup.executor_errors import BackupPathOccupied
from secret_agents_setup.link_errors import SymlinkPrivilegeRequired
from secret_agents_setup.links import LinkBackend
from secret_agents_setup.models import (
    Harness,
    InstallReceipt,
    ProjectionKind,
    ReceiptBackup,
    ReceiptProjection,
)
from secret_agents_setup.receipts import receipt_path, write_receipt_atomic

CLOCK = datetime(2026, 8, 29, 12, 0, 0)


class FakeBackend:
    """Simulates links with placeholder files and a target map; records calls."""

    def __init__(self, *, probe_error: Exception | None = None) -> None:
        self.calls: list[tuple[str, Path]] = []
        self.targets: dict[Path, Path] = {}
        self.probe_error = probe_error
        self.fail_on: Callable[[tuple[str, Path]], bool] | None = None

    def probe_file_link_capability(self, probe_root: Path) -> None:
        self.calls.append(("probe", probe_root))
        if self.probe_error is not None:
            raise self.probe_error

    def create_directory_link(self, src: Path, dst: Path) -> None:
        self._maybe_fail(("create", dst))
        dst.mkdir()
        self.targets[dst] = src.resolve()
        self.calls.append(("create", dst))

    def create_file_link(self, src: Path, dst: Path) -> None:
        self._maybe_fail(("create", dst))
        dst.write_text("link", encoding="utf-8")
        self.targets[dst] = src.resolve()
        self.calls.append(("create", dst))

    def remove_link(self, path: Path) -> None:
        self._maybe_fail(("remove", path))
        if path.is_dir():
            path.rmdir()
        elif path.is_symlink() or path.exists():
            path.unlink()
        self.targets.pop(path, None)
        self.calls.append(("remove", path))

    def resolved_target(self, path: Path) -> Path:
        return self.targets.get(path, path.resolve())

    def _maybe_fail(self, tag: tuple[str, Path]) -> None:
        if self.fail_on is not None and self.fail_on(tag):
            raise RuntimeError(f"injected failure at {tag[0]} {tag[1].name}")


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


def _run(args: list[str], *, home: Path, root: Path, os_name: str = "posix", backend: LinkBackend | None = None) -> int:
    return main(
        [*args, "--agent-root", str(root)],
        environment={},
        home=home,
        script_path=root,
        os_name=os_name,
        now=lambda: CLOCK,
        backend=backend,
    )


def test_invalid_selector_is_invalid_input(tmp_path: Path) -> None:
    root = _make_agent_root(tmp_path)
    assert _run(["install", "--harness", "mystery"], home=tmp_path / "home", root=root) == ExitCode.INVALID_INPUT


def test_backup_conflicts_flag_rejected_on_uninstall(tmp_path: Path) -> None:
    root = _make_agent_root(tmp_path)
    assert _run(["uninstall", "--backup-conflicts"], home=tmp_path / "home", root=root) == ExitCode.INVALID_INPUT


def test_unresolved_root_is_invalid_input(tmp_path: Path) -> None:
    code = main(
        ["install"],
        environment={},
        home=tmp_path / "home",
        script_path=tmp_path / "nowhere" / "script.py",
        os_name="posix",
        now=lambda: CLOCK,
    )
    assert code == ExitCode.INVALID_INPUT


def test_dry_run_reports_plan_without_mutation(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _make_agent_root(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    backend = FakeBackend()

    code = _run(["install", "--harness", "codex", "--dry-run"], home=home, root=root, backend=backend)

    assert code == ExitCode.SUCCESS
    assert backend.calls == []
    assert not (home / ".agents").exists()
    out = capsys.readouterr().out
    assert "root" in out


def test_windows_dry_run_notes_capability_unverified(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _make_agent_root(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    backend = FakeBackend()

    code = _run(["install", "--harness", "codex", "--dry-run"], home=home, root=root, os_name="nt", backend=backend)

    assert code == ExitCode.SUCCESS
    assert backend.calls == []
    assert "capability-unverified-until-install" in capsys.readouterr().out


def test_install_creates_projections_and_writes_receipt(tmp_path: Path) -> None:
    root = _make_agent_root(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    backend = FakeBackend()

    code = _run(["install", "--harness", "codex"], home=home, root=root, backend=backend)

    assert code == ExitCode.SUCCESS
    assert ("probe", home) in backend.calls
    assert (home / ".agents" / "skills").exists()
    assert (home / ".codex" / "AGENTS.md").exists()
    assert receipt_path(home, "handbag-secret-agents").exists()


def test_capability_refusal_blocks_before_mutation(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _make_agent_root(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    backend = FakeBackend(probe_error=SymlinkPrivilegeRequired())

    code = _run(["install", "--harness", "codex"], home=home, root=root, backend=backend)

    assert code == ExitCode.BLOCKED
    assert not (home / ".agents").exists()
    assert not (home / ".codex").exists()
    assert "Developer Mode or elevation" in capsys.readouterr().err


def test_blocked_plan_does_not_mutate(tmp_path: Path) -> None:
    root = _make_agent_root(tmp_path)
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)
    (home / ".codex" / "AGENTS.md").write_text("personal", encoding="utf-8")  # unrelated file blocks
    backend = FakeBackend()

    code = _run(["install", "--harness", "codex"], home=home, root=root, backend=backend)

    assert code == ExitCode.BLOCKED
    assert backend.calls == []
    assert (home / ".codex" / "AGENTS.md").read_text(encoding="utf-8") == "personal"


def test_execution_failure_returns_execution_failed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _make_agent_root(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    backend = FakeBackend()
    backend.fail_on = lambda tag: tag[0] == "create" and tag[1].name == "AGENTS.md"

    code = _run(["install", "--harness", "codex"], home=home, root=root, backend=backend)

    assert code == ExitCode.EXECUTION_FAILED
    assert not (home / ".agents").exists()
    assert capsys.readouterr().err != ""


def test_backup_path_occupied_is_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _make_agent_root(tmp_path)
    home = tmp_path / "home"
    guidance = home / ".codex" / "AGENTS.md"
    guidance.parent.mkdir(parents=True)
    guidance.write_text("personal", encoding="utf-8")
    occupied = guidance.with_name("AGENTS.md.backup-20260829-120000")

    def raise_occupied(*_args: object, **_kwargs: object) -> None:
        raise BackupPathOccupied(occupied)

    monkeypatch.setattr(cli_module, "apply_install_plan", raise_occupied)

    code = _run(["install", "--harness", "codex", "--backup-conflicts"], home=home, root=root, backend=FakeBackend())

    captured = capsys.readouterr()
    assert code == ExitCode.BLOCKED
    assert "result blocked" in captured.out
    assert str(occupied) in captured.err
    assert "result failed" not in captured.out


def test_check_missing_is_blocked(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _make_agent_root(tmp_path)
    home = tmp_path / "home"
    home.mkdir()

    code = _run(["check", "--harness", "codex"], home=home, root=root)

    assert code == ExitCode.BLOCKED
    assert "missing" in capsys.readouterr().out


def test_check_all_correct_is_success(tmp_path: Path) -> None:
    root = _make_agent_root(tmp_path)
    home = tmp_path / "home"
    codex_dir = home / ".codex"
    agents_dir = home / ".agents"
    codex_dir.mkdir(parents=True)
    agents_dir.mkdir(parents=True)
    try:
        (agents_dir / "skills").symlink_to(root / "skills", target_is_directory=True)
        (codex_dir / "AGENTS.md").symlink_to(root / "AGENTS.md")
    except OSError as exc:  # pragma: no cover - unprivileged Windows
        pytest.skip(f"host cannot create the real links this check needs: {exc}")

    code = _run(["check", "--harness", "codex"], home=home, root=root)

    assert code == ExitCode.SUCCESS


def test_uninstall_without_receipt_is_success(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _make_agent_root(tmp_path)
    home = tmp_path / "home"
    home.mkdir()

    code = _run(["uninstall", "--harness", "all"], home=home, root=root, backend=FakeBackend())

    assert code == ExitCode.SUCCESS
    assert "not-installed" in capsys.readouterr().out


def test_uninstall_foreign_content_blocks(tmp_path: Path) -> None:
    root = _make_agent_root(tmp_path)
    home = tmp_path / "home"
    guidance = home / ".codex" / "AGENTS.md"
    guidance.parent.mkdir(parents=True)
    guidance.write_text("user replaced this", encoding="utf-8")
    receipt = InstallReceipt(
        schema_version=1,
        root_identity="handbag-secret-agents",
        installed_root=root,
        projections=(ReceiptProjection(guidance, root / "AGENTS.md", ProjectionKind.GUIDANCE, (Harness.CODEX,)),),
        backups=(),
        created_parents=(),
    )
    write_receipt_atomic(receipt, receipt_path(home, "handbag-secret-agents"))

    code = _run(["uninstall", "--harness", "codex"], home=home, root=root, backend=FakeBackend())

    assert code == ExitCode.BLOCKED


def test_uninstall_restores_backup_and_retains_shared(tmp_path: Path) -> None:
    root = _make_agent_root(tmp_path)
    home = tmp_path / "home"
    backend = FakeBackend()
    shared = home / ".agents" / "skills"
    shared.parent.mkdir(parents=True)
    shared.mkdir()
    backend.targets[shared] = (root / "skills").resolve()
    guidance = home / ".codex" / "AGENTS.md"
    guidance.parent.mkdir(parents=True)
    guidance.write_text("link", encoding="utf-8")
    backend.targets[guidance] = (root / "AGENTS.md").resolve()
    backup = guidance.with_name("AGENTS.md.backup-20260101-000000")
    backup.write_text("original", encoding="utf-8")
    receipt = InstallReceipt(
        schema_version=1,
        root_identity="handbag-secret-agents",
        installed_root=root,
        projections=(
            ReceiptProjection(shared, root / "skills", ProjectionKind.SKILLS, (Harness.CODEX, Harness.COPILOT)),
            ReceiptProjection(guidance, root / "AGENTS.md", ProjectionKind.GUIDANCE, (Harness.CODEX,)),
        ),
        backups=(ReceiptBackup(original=guidance, backup=backup, sha256=hashlib.sha256(b"original").hexdigest()),),
        created_parents=(),
    )
    receipt_file = receipt_path(home, "handbag-secret-agents")
    write_receipt_atomic(receipt, receipt_file)

    code = _run(["uninstall", "--harness", "codex"], home=home, root=root, backend=backend)

    assert code == ExitCode.SUCCESS
    assert guidance.read_text(encoding="utf-8") == "original"  # backup restored
    assert shared.is_dir()  # shared skills link retained for copilot
    loaded_projections = _load_receipt_projections(receipt_file)
    assert loaded_projections == {shared}  # only the shared retained projection remains


def test_shared_skill_destination_appears_once(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _make_agent_root(tmp_path)
    home = tmp_path / "home"
    home.mkdir()

    _run(["check", "--harness", "all"], home=home, root=root)

    out = capsys.readouterr().out
    assert out.count(str(home / ".agents" / "skills")) == 1


def _load_receipt_projections(receipt_file: Path) -> set[Path]:
    from secret_agents_setup.receipts import load_receipt

    receipt = load_receipt(receipt_file, expected_identity="handbag-secret-agents", home=receipt_file.parents[2])
    assert receipt is not None
    return {projection.destination for projection in receipt.projections}
