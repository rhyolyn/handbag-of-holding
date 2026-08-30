"""Tests for journaled install execution, rollback, and post-install validation."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest

import secret_agents_setup.executor as executor_module
import secret_agents_setup.link_errors as link_errors
from secret_agents_setup.executor import apply_install_plan, validate_installed_plan
from secret_agents_setup.executor_errors import BackupPathOccupied, ExecutionError
from secret_agents_setup.harness_profiles import (
    InstructionsMapping,
    SkillsMapping,
    build_install_mappings,
)
from secret_agents_setup.link_errors import LinkTargetMismatch, SymlinkUnsupported
from secret_agents_setup.models import (
    AgentRoot,
    ExecutionEventKind,
    ExecutionReport,
    Harness,
)
from secret_agents_setup.planning import (
    BackupFile,
    CreateLink,
    InstallPlan,
    InstallState,
    PathStatus,
    ReplaceLink,
)
from secret_agents_setup.receipts import (
    InstallReceipt,
    OwnedBackup,
    OwnedLink,
    receipt_path,
    write_receipt_atomic,
)

IDENTITY = "handbag-secret-agents"
TIMESTAMP = datetime(2026, 8, 29, 12, 0, 0)


class RecordingBackend:
    """A LinkBackend that records calls and simulates links with placeholder files."""

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


def _make_root(tmp_path: Path, name: str = "canonical") -> AgentRoot:
    root = tmp_path / name
    (root / "skills" / "alpha").mkdir(parents=True)
    (root / "skills" / "alpha" / "SKILL.md").write_text("---\nname: alpha\n---\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("guidance", encoding="utf-8")
    (root / "model-routing.json").write_text("{}", encoding="utf-8")
    (root / "runbooks").mkdir()
    return AgentRoot(path=root, schema_version=1, identity=IDENTITY)


def _event_kinds(report: ExecutionReport) -> list[ExecutionEventKind]:
    return [event.kind for event in report.events]


def _instructions_mapping(root: AgentRoot, home: Path, harnesses: tuple[Harness, ...]) -> InstructionsMapping:
    return InstructionsMapping(
        harnesses=harnesses,
        source=root.path / "AGENTS.md",
        destination=home / ".codex" / "AGENTS.md",
    )


def _skills_mapping(root: AgentRoot, home: Path, harnesses: tuple[Harness, ...]) -> SkillsMapping:
    return SkillsMapping(
        harnesses=harnesses,
        source=root.path / "skills",
        destination=home / ".agents" / "skills",
    )


def test_install_probes_creates_parents_and_writes_receipt(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    probe_root = tmp_path / "probe"
    probe_root.mkdir()
    mappings = build_install_mappings(root, home, (Harness.CODEX,))
    from secret_agents_setup.planning import build_install_plan

    plan = build_install_plan(mappings, (), False, TIMESTAMP)
    backend = RecordingBackend()
    receipt_file = receipt_path(home, root.identity)

    report = apply_install_plan(plan, root, probe_root, backend, receipt_file, None)

    assert backend.calls[0] == ("probe", probe_root)
    assert _event_kinds(report) == [
        ExecutionEventKind.PROBED_CAPABILITY,
        ExecutionEventKind.CREATED_PARENT,
        ExecutionEventKind.CREATED_LINK,
        ExecutionEventKind.CREATED_PARENT,
        ExecutionEventKind.CREATED_LINK,
        ExecutionEventKind.WROTE_RECEIPT,
    ]
    assert report.receipt_written is True
    assert receipt_file.exists()
    assert report.receipt is not None
    assert report.receipt.root_identity == IDENTITY
    assert report.receipt.installed_root == root.path
    destinations = {link.mapping.destination for link in report.receipt.links}
    assert destinations == {home / ".agents" / "skills", home / ".codex" / "AGENTS.md"}
    assert set(report.receipt.created_parents) == {home / ".agents", home / ".codex"}


def test_backup_action_captures_sha256_before_link(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)
    original = home / ".codex" / "AGENTS.md"
    original.write_text("personal", encoding="utf-8")
    probe_root = tmp_path / "probe"
    probe_root.mkdir()
    projection = _instructions_mapping(root, home, (Harness.CODEX,))
    backup = original.with_name("AGENTS.md.backup-20260829-120000")
    plan = InstallPlan(
        statuses=(PathStatus(InstallState.BACKUP_PLANNED, projection),),
        changes=(
            BackupFile(original, backup),
            CreateLink(projection),
        ),
    )
    backend = RecordingBackend()
    receipt_file = receipt_path(home, root.identity)

    report = apply_install_plan(plan, root, probe_root, backend, receipt_file, None)

    assert backup.read_text(encoding="utf-8") == "personal"
    assert report.receipt is not None
    assert report.receipt.backups == (
        OwnedBackup(original=original, backup=backup, sha256=hashlib.sha256(b"personal").hexdigest()),
    )
    assert ExecutionEventKind.BACKED_UP in _event_kinds(report)


def test_backup_race_never_overwrites_existing_bytes(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)
    original = home / ".codex" / "AGENTS.md"
    original.write_bytes(b"personal bytes")
    probe_root = tmp_path / "probe"
    probe_root.mkdir()
    projection = _instructions_mapping(root, home, (Harness.CODEX,))
    from secret_agents_setup.planning import build_install_plan

    plan = build_install_plan((projection,), (), True, TIMESTAMP)
    backup = next(change.backup for change in plan.changes if isinstance(change, BackupFile))
    backup.write_bytes(b"occupied bytes")
    backend = RecordingBackend()
    receipt_file = receipt_path(home, root.identity)

    with pytest.raises(BackupPathOccupied) as raised:
        apply_install_plan(plan, root, probe_root, backend, receipt_file, None)

    assert raised.value.path == backup
    assert original.read_bytes() == b"personal bytes"
    assert backup.read_bytes() == b"occupied bytes"
    assert backend.targets == {}
    assert not receipt_file.exists()


def test_backup_race_with_prior_rollback_failure_reports_execution_error(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    home = tmp_path / "home"
    (home / ".agents").mkdir(parents=True)
    guidance = home / ".codex" / "AGENTS.md"
    guidance.parent.mkdir(parents=True)
    guidance.write_bytes(b"personal bytes")
    probe_root = tmp_path / "probe"
    probe_root.mkdir()
    mappings = build_install_mappings(root, home, (Harness.CODEX,))
    from secret_agents_setup.planning import build_install_plan

    plan = build_install_plan(mappings, (), True, TIMESTAMP)
    backup = next(change.backup for change in plan.changes if isinstance(change, BackupFile))
    backup.write_bytes(b"occupied bytes")
    earlier_link = home / ".agents" / "skills"
    backend = RecordingBackend()
    backend.fail_on = lambda tag: tag == ("remove", earlier_link)
    receipt_file = receipt_path(home, root.identity)

    with pytest.raises(ExecutionError) as raised:
        apply_install_plan(plan, root, probe_root, backend, receipt_file, None)

    error = raised.value
    assert isinstance(error.original, BackupPathOccupied)
    assert error.original.path == backup
    assert error.__cause__ is error.original
    assert len(error.rollback_failures) == 1
    rollback_failure = error.rollback_failures[0]
    assert rollback_failure.operation == "remove-link"
    assert rollback_failure.path == earlier_link
    assert rollback_failure.detail == "injected failure at remove skills"
    assert error.recoverable_paths == (earlier_link,)
    assert earlier_link.exists()
    assert guidance.read_bytes() == b"personal bytes"
    assert backup.read_bytes() == b"occupied bytes"
    assert not receipt_file.exists()


def test_failed_backup_move_removes_its_reservation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_root(tmp_path)
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)
    original = home / ".codex" / "AGENTS.md"
    original.write_text("personal", encoding="utf-8")
    backup = original.with_name("AGENTS.md.backup-20260829-120000")
    projection = _instructions_mapping(root, home, (Harness.CODEX,))
    plan = InstallPlan(
        statuses=(PathStatus(InstallState.BACKUP_PLANNED, projection),),
        changes=(BackupFile(original, backup),),
    )

    def fail_move(source: Path, destination: Path) -> None:
        assert source == original
        assert destination == backup
        assert backup.exists()
        raise OSError("move failed")

    monkeypatch.setattr(os, "replace", fail_move)

    with pytest.raises(ExecutionError) as raised:
        apply_install_plan(plan, root, tmp_path / "probe", RecordingBackend(), receipt_path(home, root.identity), None)

    assert isinstance(raised.value.original, OSError)
    assert original.read_text(encoding="utf-8") == "personal"
    assert not backup.exists()


def test_failed_backup_cleanup_does_not_mask_original_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_root(tmp_path)
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)
    original = home / ".codex" / "AGENTS.md"
    original.write_text("personal", encoding="utf-8")
    backup = original.with_name("AGENTS.md.backup-20260829-120000")
    projection = _instructions_mapping(root, home, (Harness.CODEX,))
    plan = InstallPlan(
        statuses=(PathStatus(InstallState.BACKUP_PLANNED, projection),),
        changes=(BackupFile(original, backup),),
    )

    def fail_move(source: Path, destination: Path) -> None:
        assert source == original
        assert destination == backup
        raise OSError("move failed")

    original_unlink = Path.unlink

    def fail_unlink(path: Path, missing_ok: bool = False) -> None:
        if path == backup:
            raise PermissionError("cleanup failed")
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(os, "replace", fail_move)
    monkeypatch.setattr(Path, "unlink", fail_unlink)

    with pytest.raises(ExecutionError) as raised:
        apply_install_plan(plan, root, tmp_path / "probe", RecordingBackend(), receipt_path(home, root.identity), None)

    assert isinstance(raised.value.original, OSError)
    assert str(raised.value.original) == "move failed"
    notes = getattr(raised.value.original, "__notes__", ())
    assert any("failed to remove reserved backup path" in note for note in notes)
    assert original.read_text(encoding="utf-8") == "personal"


def test_correct_links_without_receipt_stay_unowned(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    home = tmp_path / "home"
    projection = _skills_mapping(root, home, (Harness.CODEX,))
    plan = InstallPlan(
        statuses=(PathStatus(InstallState.CURRENT, projection),),
        changes=(),
    )
    backend = RecordingBackend()
    receipt_file = receipt_path(home, root.identity)

    report = apply_install_plan(plan, root, tmp_path / "probe", backend, receipt_file, None)

    assert report.receipt is None
    assert report.receipt_written is False
    assert report.events == ()
    assert not receipt_file.exists()
    assert backend.calls == []


def test_idempotent_owned_install_does_not_rewrite(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    home = tmp_path / "home"
    skills = _skills_mapping(root, home, (Harness.CODEX,))
    receipt = InstallReceipt(
        schema_version=1,
        root_identity=IDENTITY,
        installed_root=root.path,
        links=(OwnedLink(SkillsMapping((Harness.CODEX,), skills.source, skills.destination)),),
        backups=(),
        created_parents=(home / ".agents",),
    )
    receipt_file = receipt_path(home, root.identity)
    write_receipt_atomic(receipt, receipt_file)
    before = receipt_file.read_bytes()
    plan = InstallPlan(
        statuses=(PathStatus(InstallState.CURRENT, skills),),
        changes=(),
    )
    backend = RecordingBackend()

    report = apply_install_plan(plan, root, tmp_path / "probe", backend, receipt_file, receipt)

    assert report.receipt_written is False
    assert report.receipt == receipt
    assert receipt_file.read_bytes() == before


def test_second_harness_updates_only_shared_receipt_metadata(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    home = tmp_path / "home"
    (home / ".agents").mkdir(parents=True)
    probe_root = tmp_path / "probe"
    probe_root.mkdir()
    shared_skills = SkillsMapping(
        harnesses=(Harness.COPILOT,),
        source=root.path / "skills",
        destination=home / ".agents" / "skills",
    )
    copilot_guidance = InstructionsMapping(
        harnesses=(Harness.COPILOT,),
        source=root.path / "AGENTS.md",
        destination=home / ".copilot" / "copilot-instructions.md",
    )
    existing = InstallReceipt(
        schema_version=1,
        root_identity=IDENTITY,
        installed_root=root.path,
        links=(OwnedLink(SkillsMapping((Harness.CODEX,), shared_skills.source, shared_skills.destination)),),
        backups=(),
        created_parents=(home / ".agents",),
    )
    receipt_file = receipt_path(home, root.identity)
    write_receipt_atomic(existing, receipt_file)
    plan = InstallPlan(
        statuses=(
            PathStatus(InstallState.CURRENT, shared_skills),
            PathStatus(InstallState.MISSING, copilot_guidance),
        ),
        changes=(CreateLink(copilot_guidance),),
    )
    backend = RecordingBackend()

    report = apply_install_plan(plan, root, probe_root, backend, receipt_file, existing)

    assert report.receipt_written is True
    assert report.receipt is not None
    shared = next(link for link in report.receipt.links if link.mapping.destination == shared_skills.destination)
    assert shared.mapping.harnesses == (Harness.CODEX, Harness.COPILOT)
    # the shared skills link is never recreated: only the copilot guidance link is
    assert ("create", shared_skills.destination) not in backend.calls
    assert ("create", copilot_guidance.destination) in backend.calls


def test_unsupported_capability_leaves_everything_unchanged(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    probe_root = tmp_path / "probe"
    probe_root.mkdir()
    mappings = build_install_mappings(root, home, (Harness.CODEX,))
    from secret_agents_setup.planning import build_install_plan

    plan = build_install_plan(mappings, (), False, TIMESTAMP)
    backend = RecordingBackend(probe_error=SymlinkUnsupported(OSError("no privilege")))
    receipt_file = receipt_path(home, root.identity)

    with pytest.raises(SymlinkUnsupported):
        apply_install_plan(plan, root, probe_root, backend, receipt_file, None)

    assert list(home.iterdir()) == []
    assert not receipt_file.exists()
    assert list(probe_root.iterdir()) == []


def test_rollback_after_link_failure_removes_prior_mutations(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    probe_root = tmp_path / "probe"
    probe_root.mkdir()
    mappings = build_install_mappings(root, home, (Harness.CODEX,))
    from secret_agents_setup.planning import build_install_plan

    plan = build_install_plan(mappings, (), False, TIMESTAMP)
    backend = RecordingBackend()
    guidance_dst = home / ".codex" / "AGENTS.md"
    backend.fail_on = lambda tag: tag == ("create", guidance_dst)
    receipt_file = receipt_path(home, root.identity)

    with pytest.raises(ExecutionError) as raised:
        apply_install_plan(plan, root, probe_root, backend, receipt_file, None)

    error = raised.value
    assert error.operation == "install"
    assert "install failed" in str(error)
    assert isinstance(error.original, RuntimeError)
    assert error.__cause__ is error.original
    assert list(home.iterdir()) == []
    assert not receipt_file.exists()


@pytest.mark.parametrize(
    "cancellation",
    [KeyboardInterrupt(), SystemExit(17), GeneratorExit()],
    ids=["keyboard-interrupt", "system-exit", "generator-exit"],
)
def test_install_cancellation_rolls_back_and_reraises_same_object(tmp_path: Path, cancellation: BaseException) -> None:
    root = _make_root(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    probe_root = tmp_path / "probe"
    probe_root.mkdir()
    mappings = build_install_mappings(root, home, (Harness.CODEX,))
    from secret_agents_setup.planning import build_install_plan

    plan = build_install_plan(mappings, (), False, TIMESTAMP)
    skills_destination = home / ".agents" / "skills"

    class CancellingBackend(RecordingBackend):
        def create_file_link(self, src: Path, dst: Path) -> None:
            raise cancellation

    backend = CancellingBackend()
    receipt_file = receipt_path(home, root.identity)

    with pytest.raises(type(cancellation)) as raised:
        apply_install_plan(plan, root, probe_root, backend, receipt_file, None)

    assert raised.value is cancellation
    assert backend.calls == [
        ("probe", probe_root),
        ("create", skills_destination),
        ("remove", skills_destination),
    ]
    assert list(home.iterdir()) == []
    assert not receipt_file.exists()


def test_install_cancellation_with_rollback_failure_notes_recoverable_path(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    home = tmp_path / "home"
    (home / ".agents").mkdir(parents=True)
    probe_root = tmp_path / "probe"
    probe_root.mkdir()
    mappings = build_install_mappings(root, home, (Harness.CODEX,))
    from secret_agents_setup.planning import build_install_plan

    plan = build_install_plan(mappings, (), False, TIMESTAMP)
    skills_destination = home / ".agents" / "skills"
    cancellation = KeyboardInterrupt()

    class CancellingBackend(RecordingBackend):
        def create_file_link(self, src: Path, dst: Path) -> None:
            raise cancellation

    backend = CancellingBackend()
    backend.fail_on = lambda tag: tag == ("remove", skills_destination)

    with pytest.raises(KeyboardInterrupt) as raised:
        apply_install_plan(plan, root, probe_root, backend, receipt_path(home, root.identity), None)

    assert raised.value is cancellation
    assert len(cancellation.__notes__) == 1
    assert str(skills_destination) in cancellation.__notes__[0]
    assert skills_destination.exists()


def test_rollback_after_backup_restores_original(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)
    original = home / ".codex" / "AGENTS.md"
    original.write_text("personal", encoding="utf-8")
    probe_root = tmp_path / "probe"
    probe_root.mkdir()
    projection = _instructions_mapping(root, home, (Harness.CODEX,))
    backup = original.with_name("AGENTS.md.backup-20260829-120000")
    plan = InstallPlan(
        statuses=(PathStatus(InstallState.BACKUP_PLANNED, projection),),
        changes=(
            BackupFile(original, backup),
            CreateLink(projection),
        ),
    )
    backend = RecordingBackend()
    backend.fail_on = lambda tag: tag == ("create", original)
    receipt_file = receipt_path(home, root.identity)

    with pytest.raises(ExecutionError):
        apply_install_plan(plan, root, probe_root, backend, receipt_file, None)

    assert original.read_text(encoding="utf-8") == "personal"
    assert not backup.exists()


def test_rollback_during_receipt_write_preserves_prior_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_root(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    probe_root = tmp_path / "probe"
    probe_root.mkdir()
    mappings = build_install_mappings(root, home, (Harness.CODEX,))
    from secret_agents_setup.planning import build_install_plan

    plan = build_install_plan(mappings, (), False, TIMESTAMP)
    backend = RecordingBackend()
    receipt_file = receipt_path(home, root.identity)
    prior = InstallReceipt(
        schema_version=1,
        root_identity=IDENTITY,
        installed_root=root.path,
        links=(),
        backups=(),
        created_parents=(),
    )
    write_receipt_atomic(prior, receipt_file)
    prior_bytes = receipt_file.read_bytes()

    def boom(receipt: InstallReceipt, path: Path) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(executor_module, "write_receipt_atomic", boom)

    with pytest.raises(ExecutionError):
        apply_install_plan(plan, root, probe_root, backend, receipt_file, prior)

    assert receipt_file.read_bytes() == prior_bytes
    # every managed guidance/skill link was rolled back; only the receipt dir remains
    assert not (home / ".agents").exists()
    assert not (home / ".codex").exists()


def test_rollback_failure_reports_recoverable_paths(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    probe_root = tmp_path / "probe"
    probe_root.mkdir()
    mappings = build_install_mappings(root, home, (Harness.CODEX,))
    from secret_agents_setup.planning import build_install_plan

    plan = build_install_plan(mappings, (), False, TIMESTAMP)
    skills_dst = home / ".agents" / "skills"
    guidance_dst = home / ".codex" / "AGENTS.md"
    backend = RecordingBackend()
    # fail forward on the guidance link, then fail again when rolling back the skills link
    backend.fail_on = lambda tag: tag in {("create", guidance_dst), ("remove", skills_dst)}
    receipt_file = receipt_path(home, root.identity)

    with pytest.raises(ExecutionError) as raised:
        apply_install_plan(plan, root, probe_root, backend, receipt_file, None)

    assert raised.value.rollback_failures
    assert skills_dst in raised.value.recoverable_paths


def test_partial_backend_cleanup_failure_reports_recoverable_path_without_journal_compensation(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    home = tmp_path / "home"
    (home / ".agents").mkdir(parents=True)
    projection = _skills_mapping(root, home, (Harness.CODEX,))
    destination = projection.destination
    create_error = LinkTargetMismatch(destination, tmp_path / "wrong", projection.source.resolve())
    cleanup_error = OSError("cleanup failed")

    class PartialCleanupBackend(RecordingBackend):
        def create_directory_link(self, src: Path, dst: Path) -> None:
            dst.mkdir()
            self.targets[dst] = src.resolve()
            raise link_errors.PartialLinkCleanupFailed(dst, create_error, cleanup_error)

    plan = InstallPlan(
        statuses=(PathStatus(InstallState.MISSING, projection),),
        changes=(CreateLink(projection),),
    )

    with pytest.raises(ExecutionError) as raised:
        apply_install_plan(
            plan,
            root,
            tmp_path / "probe",
            PartialCleanupBackend(),
            receipt_path(home, root.identity),
            None,
        )

    error = raised.value
    assert isinstance(error.original, link_errors.PartialLinkCleanupFailed)
    assert error.rollback_failures == ()
    assert error.recoverable_paths == (destination,)
    assert destination.exists()


def test_relocation_retargets_and_preserves_backups(tmp_path: Path) -> None:
    old_root = _make_root(tmp_path, "old")
    new_root = _make_root(tmp_path, "new")
    home = tmp_path / "home"
    skills_dst = home / ".agents" / "skills"
    skills_dst.mkdir(parents=True)
    probe_root = tmp_path / "probe"
    probe_root.mkdir()
    new_skills = _skills_mapping(new_root, home, (Harness.CODEX,))
    backend = RecordingBackend()
    backend.targets[skills_dst] = (old_root.path / "skills").resolve()
    kept_backup = OwnedBackup(
        original=home / ".codex" / "AGENTS.md",
        backup=home / ".codex" / "AGENTS.md.backup-20260101-000000",
        sha256="b" * 64,
    )
    existing = InstallReceipt(
        schema_version=1,
        root_identity=IDENTITY,
        installed_root=old_root.path,
        links=(OwnedLink(SkillsMapping((Harness.CODEX,), old_root.path / "skills", skills_dst)),),
        backups=(kept_backup,),
        created_parents=(home / ".agents",),
    )
    receipt_file = receipt_path(home, IDENTITY)
    write_receipt_atomic(existing, receipt_file)
    plan = InstallPlan(
        statuses=(PathStatus(InstallState.STALE_LINK, new_skills),),
        changes=(ReplaceLink(new_skills),),
    )

    report = apply_install_plan(plan, new_root, probe_root, backend, receipt_file, existing)

    assert report.receipt is not None
    assert report.receipt.installed_root == new_root.path
    relocated = next(link for link in report.receipt.links if link.mapping.destination == skills_dst)
    assert relocated.mapping.source == new_root.path / "skills"
    assert report.receipt.backups == (kept_backup,)
    assert backend.targets[skills_dst] == (new_root.path / "skills").resolve()


def test_relocation_failure_restores_prior_links_and_receipt_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_root = _make_root(tmp_path, "old")
    new_root = _make_root(tmp_path, "new")
    home = tmp_path / "home"
    skills_dst = home / ".agents" / "skills"
    skills_dst.mkdir(parents=True)
    probe_root = tmp_path / "probe"
    probe_root.mkdir()
    new_skills = _skills_mapping(new_root, home, (Harness.CODEX,))
    backend = RecordingBackend()
    backend.targets[skills_dst] = (old_root.path / "skills").resolve()
    existing = InstallReceipt(
        schema_version=1,
        root_identity=IDENTITY,
        installed_root=old_root.path,
        links=(OwnedLink(SkillsMapping((Harness.CODEX,), old_root.path / "skills", skills_dst)),),
        backups=(),
        created_parents=(home / ".agents",),
    )
    receipt_file = receipt_path(home, IDENTITY)
    write_receipt_atomic(existing, receipt_file)
    prior_bytes = receipt_file.read_bytes()
    plan = InstallPlan(
        statuses=(PathStatus(InstallState.STALE_LINK, new_skills),),
        changes=(ReplaceLink(new_skills),),
    )

    def boom(receipt: InstallReceipt, path: Path) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(executor_module, "write_receipt_atomic", boom)

    with pytest.raises(ExecutionError):
        apply_install_plan(plan, new_root, probe_root, backend, receipt_file, existing)

    assert receipt_file.read_bytes() == prior_bytes
    assert backend.targets[skills_dst] == (old_root.path / "skills").resolve()


def test_validate_installed_plan_flags_mismatch(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    home = tmp_path / "home"
    projection = _skills_mapping(root, home, (Harness.CODEX,))
    plan = InstallPlan(
        statuses=(PathStatus(InstallState.MISSING, projection),),
        changes=(CreateLink(projection),),
    )
    backend = RecordingBackend()
    # backend reports the wrong target for the destination
    backend.targets[projection.destination] = tmp_path / "wrong"

    statuses = validate_installed_plan(plan, backend)

    assert statuses
    assert all(status.state is not InstallState.CURRENT for status in statuses)


def test_apply_blocked_plan_is_programmer_error(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    home = tmp_path / "home"
    projection = _skills_mapping(root, home, (Harness.CODEX,))
    plan = InstallPlan(
        statuses=(PathStatus(InstallState.SKILL_NAME_COLLISION, projection),),
        changes=(),
    )
    backend = RecordingBackend()

    with pytest.raises(ValueError, match="blocked"):
        apply_install_plan(plan, root, tmp_path / "probe", backend, receipt_path(home, IDENTITY), None)
