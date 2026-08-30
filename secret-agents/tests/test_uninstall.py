"""Tests for safe uninstall planning and journaled uninstall execution."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

import pytest

from secret_agents_setup.executor import apply_uninstall_plan
from secret_agents_setup.executor_errors import ExecutionError
from secret_agents_setup.harness_profiles import InstructionsMapping, SkillsMapping
from secret_agents_setup.models import ExecutionEventKind, Harness
from secret_agents_setup.planning import (
    DeleteReceipt,
    RemovalState,
    RemoveDirectory,
    RemoveLink,
    UninstallPlan,
    WriteReceipt,
    build_uninstall_plan,
)
from secret_agents_setup.receipts import (
    InstallReceipt,
    OwnedBackup,
    OwnedLink,
    receipt_path,
    write_receipt_atomic,
)

IDENTITY = "handbag-secret-agents"


class RecordingBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Path]] = []
        self.targets: dict[Path, Path] = {}
        self.fail_on: Callable[[tuple[str, Path]], bool] | None = None

    def probe_file_link_capability(self, probe_root: Path) -> None:
        self.calls.append(("probe", probe_root))

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


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "canonical"
    (root / "skills").mkdir(parents=True)
    (root / "AGENTS.md").write_text("guidance", encoding="utf-8")
    return root


def _owned_skills_link(backend: RecordingBackend, source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    backend.targets[destination] = source.resolve()


def _owned_file_link(backend: RecordingBackend, source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("link", encoding="utf-8")
    backend.targets[destination] = source.resolve()


def _states(plan: UninstallPlan) -> set[RemovalState]:
    return {status.state for status in plan.statuses}


def test_no_receipt_is_idempotent_not_installed(tmp_path: Path) -> None:
    plan = build_uninstall_plan(
        None, (Harness.ALL,), RecordingBackend(), expected_identity=IDENTITY, home=tmp_path / "home"
    )

    assert plan.is_blocked is False
    assert plan.changes == ()
    assert _states(plan) == {RemovalState.NOT_INSTALLED}


def test_full_uninstall_removes_owned_links_and_deletes_receipt(tmp_path: Path) -> None:
    root = _root(tmp_path)
    home = tmp_path / "home"
    backend = RecordingBackend()
    skills_dst = home / ".agents" / "skills"
    guidance_dst = home / ".codex" / "AGENTS.md"
    _owned_skills_link(backend, root / "skills", skills_dst)
    _owned_file_link(backend, root / "AGENTS.md", guidance_dst)
    receipt = InstallReceipt(
        schema_version=1,
        root_identity=IDENTITY,
        installed_root=root,
        links=(
            OwnedLink(SkillsMapping((Harness.CODEX,), root / "skills", skills_dst)),
            OwnedLink(InstructionsMapping((Harness.CODEX,), root / "AGENTS.md", guidance_dst)),
        ),
        backups=(),
        created_parents=(home / ".agents", home / ".codex"),
    )

    plan = build_uninstall_plan(receipt, (Harness.ALL,), backend, expected_identity=IDENTITY, home=home)

    assert plan.is_blocked is False
    types = [type(change) for change in plan.changes]
    assert types[:2] == [RemoveLink, RemoveLink]
    assert RemoveDirectory in types
    assert isinstance(plan.changes[-1], DeleteReceipt)
    assert RemovalState.OWNED in _states(plan)


def test_missing_owned_link_is_safe_noop(tmp_path: Path) -> None:
    root = _root(tmp_path)
    home = tmp_path / "home"
    backend = RecordingBackend()
    skills_dst = home / ".agents" / "skills"  # never created on disk
    receipt = InstallReceipt(
        schema_version=1,
        root_identity=IDENTITY,
        installed_root=root,
        links=(OwnedLink(SkillsMapping((Harness.CODEX,), root / "skills", skills_dst)),),
        backups=(),
        created_parents=(),
    )

    plan = build_uninstall_plan(receipt, (Harness.CODEX,), backend, expected_identity=IDENTITY, home=home)

    assert plan.is_blocked is False
    assert RemovalState.MISSING_OWNED_LINK in _states(plan)
    assert all(not isinstance(change, RemoveLink) for change in plan.changes)


def test_replaced_regular_file_blocks(tmp_path: Path) -> None:
    root = _root(tmp_path)
    home = tmp_path / "home"
    backend = RecordingBackend()
    guidance_dst = home / ".codex" / "AGENTS.md"
    guidance_dst.parent.mkdir(parents=True)
    guidance_dst.write_text("user rewrote this", encoding="utf-8")  # not a link, targets unset
    receipt = InstallReceipt(
        schema_version=1,
        root_identity=IDENTITY,
        installed_root=root,
        links=(OwnedLink(InstructionsMapping((Harness.CODEX,), root / "AGENTS.md", guidance_dst)),),
        backups=(),
        created_parents=(),
    )

    plan = build_uninstall_plan(receipt, (Harness.CODEX,), backend, expected_identity=IDENTITY, home=home)

    assert plan.is_blocked is True
    assert plan.changes == ()
    assert RemovalState.FOREIGN_CONTENT in _states(plan)


def test_retargeted_link_blocks(tmp_path: Path) -> None:
    root = _root(tmp_path)
    other = tmp_path / "other-checkout" / "skills"
    other.mkdir(parents=True)
    home = tmp_path / "home"
    backend = RecordingBackend()
    skills_dst = home / ".agents" / "skills"
    skills_dst.mkdir(parents=True)
    backend.targets[skills_dst] = other.resolve()  # points somewhere else now
    receipt = InstallReceipt(
        schema_version=1,
        root_identity=IDENTITY,
        installed_root=root,
        links=(OwnedLink(SkillsMapping((Harness.CODEX,), root / "skills", skills_dst)),),
        backups=(),
        created_parents=(),
    )

    plan = build_uninstall_plan(receipt, (Harness.CODEX,), backend, expected_identity=IDENTITY, home=home)

    assert plan.is_blocked is True
    assert RemovalState.FOREIGN_CONTENT in _states(plan)


def test_shared_link_retained_for_unselected_harness(tmp_path: Path) -> None:
    root = _root(tmp_path)
    home = tmp_path / "home"
    backend = RecordingBackend()
    shared_dst = home / ".agents" / "skills"
    _owned_skills_link(backend, root / "skills", shared_dst)
    receipt = InstallReceipt(
        schema_version=1,
        root_identity=IDENTITY,
        installed_root=root,
        links=(OwnedLink(SkillsMapping((Harness.CODEX, Harness.COPILOT), root / "skills", shared_dst)),),
        backups=(),
        created_parents=(),
    )

    plan = build_uninstall_plan(receipt, (Harness.CODEX,), backend, expected_identity=IDENTITY, home=home)

    assert plan.is_blocked is False
    assert RemovalState.SHARED_RETAINED in _states(plan)
    assert all(not isinstance(change, RemoveLink) for change in plan.changes)
    assert isinstance(plan.changes[-1], WriteReceipt)
    retained = plan.changes[-1].receipt.links[0]
    assert retained.mapping.harnesses == (Harness.COPILOT,)


def test_backup_missing_blocks(tmp_path: Path) -> None:
    root = _root(tmp_path)
    home = tmp_path / "home"
    backend = RecordingBackend()
    guidance_dst = home / ".codex" / "AGENTS.md"
    _owned_file_link(backend, root / "AGENTS.md", guidance_dst)
    receipt = InstallReceipt(
        schema_version=1,
        root_identity=IDENTITY,
        installed_root=root,
        links=(OwnedLink(InstructionsMapping((Harness.CODEX,), root / "AGENTS.md", guidance_dst)),),
        backups=(
            OwnedBackup(
                original=guidance_dst,
                backup=guidance_dst.with_name("AGENTS.md.backup-20260101-000000"),
                sha256="a" * 64,
            ),
        ),
        created_parents=(),
    )

    plan = build_uninstall_plan(receipt, (Harness.CODEX,), backend, expected_identity=IDENTITY, home=home)

    assert plan.is_blocked is True
    assert RemovalState.BACKUP_MISSING in _states(plan)


def test_backup_modified_blocks(tmp_path: Path) -> None:
    root = _root(tmp_path)
    home = tmp_path / "home"
    backend = RecordingBackend()
    guidance_dst = home / ".codex" / "AGENTS.md"
    _owned_file_link(backend, root / "AGENTS.md", guidance_dst)
    backup = guidance_dst.with_name("AGENTS.md.backup-20260101-000000")
    backup.write_text("changed since backup", encoding="utf-8")
    receipt = InstallReceipt(
        schema_version=1,
        root_identity=IDENTITY,
        installed_root=root,
        links=(OwnedLink(InstructionsMapping((Harness.CODEX,), root / "AGENTS.md", guidance_dst)),),
        backups=(OwnedBackup(original=guidance_dst, backup=backup, sha256="a" * 64),),
        created_parents=(),
    )

    plan = build_uninstall_plan(receipt, (Harness.CODEX,), backend, expected_identity=IDENTITY, home=home)

    assert plan.is_blocked is True
    assert RemovalState.BACKUP_MODIFIED in _states(plan)


def test_non_empty_created_parent_is_preserved(tmp_path: Path) -> None:
    root = _root(tmp_path)
    home = tmp_path / "home"
    backend = RecordingBackend()
    skills_dst = home / ".agents" / "skills"
    _owned_skills_link(backend, root / "skills", skills_dst)
    # a third-party sibling makes the installer-created parent non-empty after removal
    (home / ".agents" / "third-party").mkdir()
    receipt = InstallReceipt(
        schema_version=1,
        root_identity=IDENTITY,
        installed_root=root,
        links=(OwnedLink(SkillsMapping((Harness.CODEX,), root / "skills", skills_dst)),),
        backups=(),
        created_parents=(home / ".agents",),
    )

    plan = build_uninstall_plan(receipt, (Harness.CODEX,), backend, expected_identity=IDENTITY, home=home)

    assert plan.is_blocked is False
    assert RemovalState.PARENT_PRESERVED in _states(plan)
    assert all(not isinstance(change, RemoveDirectory) for change in plan.changes)


def test_foreign_identity_blocks(tmp_path: Path) -> None:
    root = _root(tmp_path)
    home = tmp_path / "home"
    receipt = InstallReceipt(
        schema_version=1,
        root_identity="someone-else",
        installed_root=root,
        links=(),
        backups=(),
        created_parents=(),
    )

    plan = build_uninstall_plan(receipt, (Harness.ALL,), RecordingBackend(), expected_identity=IDENTITY, home=home)

    assert plan.is_blocked is True
    assert RemovalState.FOREIGN_CONTENT in _states(plan)


def test_out_of_home_path_blocks(tmp_path: Path) -> None:
    root = _root(tmp_path)
    home = tmp_path / "home"
    escaping = tmp_path / "elsewhere" / "skills"
    receipt = InstallReceipt(
        schema_version=1,
        root_identity=IDENTITY,
        installed_root=root,
        links=(OwnedLink(SkillsMapping((Harness.CODEX,), root / "skills", escaping)),),
        backups=(),
        created_parents=(),
    )

    plan = build_uninstall_plan(receipt, (Harness.ALL,), RecordingBackend(), expected_identity=IDENTITY, home=home)

    assert plan.is_blocked is True
    assert RemovalState.FOREIGN_CONTENT in _states(plan)


def test_destination_below_linked_parent_outside_home_blocks(tmp_path: Path) -> None:
    root = _root(tmp_path)
    home = tmp_path / "home"
    outside = tmp_path / "outside"
    home.mkdir()
    outside.mkdir()
    try:
        (home / ".codex").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"host cannot create parent symlink: {exc}")
    destination = home / ".codex" / "AGENTS.md"
    destination.write_text("link", encoding="utf-8")
    backend = RecordingBackend()
    backend.targets[destination] = (root / "AGENTS.md").resolve()
    receipt = InstallReceipt(
        schema_version=1,
        root_identity=IDENTITY,
        installed_root=root,
        links=(OwnedLink(InstructionsMapping((Harness.CODEX,), root / "AGENTS.md", destination)),),
        backups=(),
        created_parents=(),
    )

    plan = build_uninstall_plan(receipt, (Harness.CODEX,), backend, expected_identity=IDENTITY, home=home)

    assert plan.is_blocked is True
    assert plan.changes == ()


def test_apply_removes_owned_restores_backup_and_preserves_third_party(tmp_path: Path) -> None:
    root = _root(tmp_path)
    home = tmp_path / "home"
    backend = RecordingBackend()
    skills_root = home / ".claude" / "skills"
    skills_root.mkdir(parents=True)
    (skills_root / "third-party").mkdir()  # not installer-owned
    alpha_dst = skills_root / "alpha"
    _owned_skills_link(backend, root / "skills" / "alpha", alpha_dst)
    guidance_dst = home / ".claude" / "CLAUDE.md"
    _owned_file_link(backend, root / "AGENTS.md", guidance_dst)
    backup = guidance_dst.with_name("CLAUDE.md.backup-20260101-000000")
    backup.write_text("original user guidance", encoding="utf-8")
    receipt = InstallReceipt(
        schema_version=1,
        root_identity=IDENTITY,
        installed_root=root,
        links=(
            OwnedLink(SkillsMapping((Harness.CLAUDE,), root / "skills" / "alpha", alpha_dst)),
            OwnedLink(InstructionsMapping((Harness.CLAUDE,), root / "AGENTS.md", guidance_dst)),
        ),
        backups=(
            OwnedBackup(
                original=guidance_dst,
                backup=backup,
                sha256=hashlib.sha256(b"original user guidance").hexdigest(),
            ),
        ),
        created_parents=(),
    )
    receipt_file = receipt_path(home, IDENTITY)
    write_receipt_atomic(receipt, receipt_file)

    plan = build_uninstall_plan(receipt, (Harness.CLAUDE,), backend, expected_identity=IDENTITY, home=home)
    assert isinstance(plan.changes[-1], (WriteReceipt, DeleteReceipt))  # receipt mutation is always last
    report = apply_uninstall_plan(plan, backend)

    assert not alpha_dst.exists()
    assert (skills_root / "third-party").is_dir()
    assert guidance_dst.read_text(encoding="utf-8") == "original user guidance"
    assert not backup.exists()
    assert not receipt_file.exists()
    assert report.receipt is None
    assert ExecutionEventKind.RESTORED_BACKUP in [event.kind for event in report.events]


def test_partial_uninstall_replaces_receipt_last(tmp_path: Path) -> None:
    root = _root(tmp_path)
    home = tmp_path / "home"
    backend = RecordingBackend()
    shared_dst = home / ".agents" / "skills"
    _owned_skills_link(backend, root / "skills", shared_dst)
    codex_guidance = home / ".codex" / "AGENTS.md"
    _owned_file_link(backend, root / "AGENTS.md", codex_guidance)
    receipt = InstallReceipt(
        schema_version=1,
        root_identity=IDENTITY,
        installed_root=root,
        links=(
            OwnedLink(SkillsMapping((Harness.CODEX, Harness.COPILOT), root / "skills", shared_dst)),
            OwnedLink(InstructionsMapping((Harness.CODEX,), root / "AGENTS.md", codex_guidance)),
        ),
        backups=(),
        created_parents=(home / ".codex",),
    )
    receipt_file = receipt_path(home, IDENTITY)
    write_receipt_atomic(receipt, receipt_file)

    plan = build_uninstall_plan(receipt, (Harness.CODEX,), backend, expected_identity=IDENTITY, home=home)
    assert isinstance(plan.changes[-1], WriteReceipt)
    report = apply_uninstall_plan(plan, backend)

    assert not codex_guidance.exists()  # codex-only guidance removed
    assert shared_dst.is_dir()  # shared skills link retained for copilot
    assert receipt_file.exists()
    assert report.receipt is not None
    assert report.receipt.links[0].mapping.harnesses == (Harness.COPILOT,)


def test_rollback_after_injected_failure_restores_links(tmp_path: Path) -> None:
    root = _root(tmp_path)
    home = tmp_path / "home"
    backend = RecordingBackend()
    skills_dst = home / ".agents" / "skills"
    guidance_dst = home / ".codex" / "AGENTS.md"
    _owned_skills_link(backend, root / "skills", skills_dst)
    _owned_file_link(backend, root / "AGENTS.md", guidance_dst)
    receipt = InstallReceipt(
        schema_version=1,
        root_identity=IDENTITY,
        installed_root=root,
        links=(
            OwnedLink(SkillsMapping((Harness.CODEX,), root / "skills", skills_dst)),
            OwnedLink(InstructionsMapping((Harness.CODEX,), root / "AGENTS.md", guidance_dst)),
        ),
        backups=(),
        created_parents=(),
    )
    receipt_file = receipt_path(home, IDENTITY)
    write_receipt_atomic(receipt, receipt_file)
    prior_bytes = receipt_file.read_bytes()
    plan = build_uninstall_plan(receipt, (Harness.CODEX,), backend, expected_identity=IDENTITY, home=home)
    # fail while deleting the receipt, after both links were removed
    backend.fail_on = lambda tag: tag == ("remove", guidance_dst)

    with pytest.raises(ExecutionError) as raised:
        apply_uninstall_plan(plan, backend)

    error = raised.value
    assert error.operation == "uninstall"
    assert "uninstall failed" in str(error)
    assert isinstance(error.original, RuntimeError)
    assert error.__cause__ is error.original
    # the first removed link is restored and the receipt bytes are intact
    assert backend.resolved_target(skills_dst) == (root / "skills").resolve()
    assert receipt_file.read_bytes() == prior_bytes


@pytest.mark.parametrize(
    "cancellation",
    [KeyboardInterrupt(), SystemExit(17), GeneratorExit()],
    ids=["keyboard-interrupt", "system-exit", "generator-exit"],
)
def test_uninstall_cancellation_rolls_back_and_reraises_same_object(
    tmp_path: Path, cancellation: BaseException
) -> None:
    root = _root(tmp_path)
    home = tmp_path / "home"
    skills_destination = home / ".agents" / "skills"
    guidance_destination = home / ".codex" / "AGENTS.md"

    class CancellingBackend(RecordingBackend):
        def remove_link(self, path: Path) -> None:
            if path == guidance_destination:
                raise cancellation
            super().remove_link(path)

    backend = CancellingBackend()
    _owned_skills_link(backend, root / "skills", skills_destination)
    _owned_file_link(backend, root / "AGENTS.md", guidance_destination)
    receipt = InstallReceipt(
        schema_version=1,
        root_identity=IDENTITY,
        installed_root=root,
        links=(
            OwnedLink(SkillsMapping((Harness.CODEX,), root / "skills", skills_destination)),
            OwnedLink(InstructionsMapping((Harness.CODEX,), root / "AGENTS.md", guidance_destination)),
        ),
        backups=(),
        created_parents=(),
    )
    receipt_file = receipt_path(home, IDENTITY)
    write_receipt_atomic(receipt, receipt_file)
    prior_bytes = receipt_file.read_bytes()
    plan = build_uninstall_plan(receipt, (Harness.CODEX,), backend, expected_identity=IDENTITY, home=home)

    with pytest.raises(type(cancellation)) as raised:
        apply_uninstall_plan(plan, backend)

    assert raised.value is cancellation
    assert backend.resolved_target(skills_destination) == (root / "skills").resolve()
    assert backend.resolved_target(guidance_destination) == (root / "AGENTS.md").resolve()
    assert receipt_file.read_bytes() == prior_bytes


def test_apply_blocked_uninstall_plan_is_programmer_error(tmp_path: Path) -> None:
    root = _root(tmp_path)
    home = tmp_path / "home"
    backend = RecordingBackend()
    guidance_dst = home / ".codex" / "AGENTS.md"
    guidance_dst.parent.mkdir(parents=True)
    guidance_dst.write_text("foreign", encoding="utf-8")
    receipt = InstallReceipt(
        schema_version=1,
        root_identity=IDENTITY,
        installed_root=root,
        links=(OwnedLink(InstructionsMapping((Harness.CODEX,), root / "AGENTS.md", guidance_dst)),),
        backups=(),
        created_parents=(),
    )
    plan = build_uninstall_plan(receipt, (Harness.CODEX,), backend, expected_identity=IDENTITY, home=home)

    with pytest.raises(ValueError, match="blocked"):
        apply_uninstall_plan(plan, backend)
