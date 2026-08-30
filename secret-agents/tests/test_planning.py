"""Tests for read-only mapping classification and install planning."""

from datetime import datetime
from pathlib import Path

from secret_agents_setup.harness_profiles import InstructionsMapping, SkillsMapping
from secret_agents_setup.models import Harness, SkillDescriptor
from secret_agents_setup.planning import (
    BackupFile,
    CreateLink,
    InstallState,
    PathStatus,
    ReplaceLink,
    build_install_plan,
)

TIMESTAMP = datetime(2026, 8, 29, 12, 34, 56)


def _instructions_mapping(source: Path, destination: Path) -> InstructionsMapping:
    return InstructionsMapping(
        harnesses=(Harness.CODEX,),
        source=source,
        destination=destination,
    )


def _skills_mapping(source: Path, destination: Path) -> SkillsMapping:
    return SkillsMapping(
        harnesses=(Harness.CLAUDE,),
        source=source,
        destination=destination,
    )


def _skill(source: Path, name: str) -> SkillDescriptor:
    return SkillDescriptor(name=name, description=f"{name} skill", directory=source / name)


def test_absent_destination_plans_link_creation(tmp_path: Path) -> None:
    source = tmp_path / "canonical" / "AGENTS.md"
    source.parent.mkdir()
    source.write_text("guidance", encoding="utf-8")
    mapping = _instructions_mapping(source, tmp_path / "home" / ".codex" / "AGENTS.md")

    plan = build_install_plan((mapping,), (), False, TIMESTAMP)

    assert plan.is_blocked is False
    assert plan.statuses == (PathStatus(InstallState.MISSING, mapping),)
    assert plan.statuses[0].path == mapping.destination
    assert plan.changes == (CreateLink(mapping),)


def test_correct_whole_directory_link_needs_no_action(tmp_path: Path) -> None:
    source = tmp_path / "canonical" / "skills"
    source.mkdir(parents=True)
    destination = tmp_path / "home" / ".agents" / "skills"
    destination.parent.mkdir(parents=True)
    destination.symlink_to(source, target_is_directory=True)
    mapping = _skills_mapping(source, destination)

    plan = build_install_plan((mapping,), (), False, TIMESTAMP)

    assert plan.statuses == (PathStatus(InstallState.CURRENT, mapping),)
    assert plan.statuses[0].state.output_name == "correct"
    assert plan.changes == ()


def test_stale_link_is_replaced(tmp_path: Path) -> None:
    source = tmp_path / "canonical" / "AGENTS.md"
    source.parent.mkdir()
    source.write_text("canonical", encoding="utf-8")
    stale_source = tmp_path / "old" / "AGENTS.md"
    stale_source.parent.mkdir()
    stale_source.write_text("old", encoding="utf-8")
    destination = tmp_path / "home" / ".codex" / "AGENTS.md"
    destination.parent.mkdir(parents=True)
    destination.symlink_to(stale_source)
    mapping = _instructions_mapping(source, destination)

    plan = build_install_plan((mapping,), (), False, TIMESTAMP)

    assert plan.statuses == (PathStatus(InstallState.STALE_LINK, mapping),)
    assert plan.changes == (ReplaceLink(mapping),)


def test_broken_link_is_distinguished_and_replaced(tmp_path: Path) -> None:
    source = tmp_path / "canonical" / "AGENTS.md"
    source.parent.mkdir()
    source.write_text("canonical", encoding="utf-8")
    destination = tmp_path / "home" / ".codex" / "AGENTS.md"
    destination.parent.mkdir(parents=True)
    destination.symlink_to(tmp_path / "missing" / "AGENTS.md")
    mapping = _instructions_mapping(source, destination)

    plan = build_install_plan((mapping,), (), False, TIMESTAMP)

    assert plan.statuses == (PathStatus(InstallState.BROKEN_LINK, mapping),)
    assert plan.changes == (ReplaceLink(mapping),)


def test_unrelated_instruction_file_conflicts_without_backup(tmp_path: Path) -> None:
    source = tmp_path / "canonical" / "AGENTS.md"
    source.parent.mkdir()
    source.write_text("canonical", encoding="utf-8")
    destination = tmp_path / "home" / ".codex" / "AGENTS.md"
    destination.parent.mkdir(parents=True)
    destination.write_text("personal", encoding="utf-8")
    mapping = _instructions_mapping(source, destination)

    plan = build_install_plan((mapping,), (), False, TIMESTAMP)

    assert plan.is_blocked is True
    assert plan.statuses == (PathStatus(InstallState.CONFLICT, mapping),)
    assert plan.statuses[0].blocks_install is True
    assert plan.statuses[0].state.output_name == "unrelated"
    assert plan.changes == ()


def test_backup_conflict_names_timestamped_sibling_before_link(tmp_path: Path) -> None:
    source = tmp_path / "canonical" / "AGENTS.md"
    source.parent.mkdir()
    source.write_text("canonical", encoding="utf-8")
    destination = tmp_path / "home" / ".codex" / "AGENTS.md"
    destination.parent.mkdir(parents=True)
    destination.write_text("personal", encoding="utf-8")
    mapping = _instructions_mapping(source, destination)

    plan = build_install_plan((mapping,), (), True, TIMESTAMP)

    assert plan.is_blocked is False
    assert plan.statuses == (PathStatus(InstallState.BACKUP_PLANNED, mapping),)
    assert plan.statuses[0].blocks_install is False
    assert plan.statuses[0].state.output_name == "unrelated"
    assert plan.changes == (
        BackupFile(destination, destination.with_name("AGENTS.md.backup-20260829-123456")),
        CreateLink(mapping),
    )


def test_backup_planning_uses_next_free_suffix(tmp_path: Path) -> None:
    source = tmp_path / "canonical" / "AGENTS.md"
    source.parent.mkdir()
    source.write_text("canonical", encoding="utf-8")
    destination = tmp_path / "home" / ".codex" / "AGENTS.md"
    destination.parent.mkdir(parents=True)
    destination.write_text("personal", encoding="utf-8")
    destination.with_name("AGENTS.md.backup-20260829-120000").write_text("occupied", encoding="utf-8")
    mapping = _instructions_mapping(source, destination)

    plan = build_install_plan((mapping,), (), True, datetime(2026, 8, 29, 12, 0, 0))

    assert plan.changes[0] == BackupFile(
        destination,
        destination.with_name("AGENTS.md.backup-20260829-120000-2"),
    )


def test_real_skill_directory_is_compatible_and_plans_each_missing_skill(tmp_path: Path) -> None:
    source = tmp_path / "canonical" / "skills"
    source.mkdir(parents=True)
    alpha = _skill(source, "alpha")
    beta = _skill(source, "beta")
    alpha.directory.mkdir()
    beta.directory.mkdir()
    destination = tmp_path / "home" / ".claude" / "skills"
    destination.mkdir(parents=True)
    (destination / "third-party").mkdir()
    mapping = _skills_mapping(source, destination)

    plan = build_install_plan((mapping,), (beta, alpha), False, TIMESTAMP)

    child_alpha = SkillsMapping(mapping.harnesses, alpha.directory, destination / "alpha")
    child_beta = SkillsMapping(mapping.harnesses, beta.directory, destination / "beta")
    assert plan.statuses == (
        PathStatus(InstallState.COMPATIBLE_SKILLS_DIRECTORY, mapping),
        PathStatus(InstallState.MISSING, child_alpha),
        PathStatus(InstallState.MISSING, child_beta),
    )
    assert plan.changes == (CreateLink(child_alpha), CreateLink(child_beta))


def test_correct_per_skill_link_is_preserved(tmp_path: Path) -> None:
    source = tmp_path / "canonical" / "skills"
    source.mkdir(parents=True)
    alpha = _skill(source, "alpha")
    alpha.directory.mkdir()
    destination = tmp_path / "home" / ".claude" / "skills"
    destination.mkdir(parents=True)
    (destination / "alpha").symlink_to(alpha.directory, target_is_directory=True)
    mapping = _skills_mapping(source, destination)

    plan = build_install_plan((mapping,), (alpha,), False, TIMESTAMP)

    child_alpha = SkillsMapping(mapping.harnesses, alpha.directory, destination / "alpha")
    assert plan.statuses == (
        PathStatus(InstallState.COMPATIBLE_SKILLS_DIRECTORY, mapping),
        PathStatus(InstallState.CURRENT, child_alpha),
    )
    assert plan.changes == ()


def test_same_name_skill_collision_blocks_entire_plan(tmp_path: Path) -> None:
    source = tmp_path / "canonical" / "skills"
    source.mkdir(parents=True)
    alpha = _skill(source, "alpha")
    alpha.directory.mkdir()
    destination = tmp_path / "home" / ".claude" / "skills"
    destination.mkdir(parents=True)
    (destination / "alpha").mkdir()
    instructions_source = tmp_path / "canonical" / "AGENTS.md"
    instructions_source.write_text("guidance", encoding="utf-8")
    missing_instructions = _instructions_mapping(instructions_source, tmp_path / "home" / ".codex" / "AGENTS.md")

    plan = build_install_plan(
        (_skills_mapping(source, destination), missing_instructions),
        (alpha,),
        False,
        TIMESTAMP,
    )

    assert plan.is_blocked is True
    collisions = [status for status in plan.statuses if status.state is InstallState.SKILL_NAME_COLLISION]
    assert len(collisions) == 1
    assert collisions[0].blocks_install is True
    assert collisions[0].mapping == SkillsMapping((Harness.CLAUDE,), alpha.directory, destination / "alpha")
    assert plan.changes == ()


def test_statuses_and_changes_have_stable_path_order(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    source_a = canonical / "A.md"
    source_z = canonical / "Z.md"
    source_a.write_text("a", encoding="utf-8")
    source_z.write_text("z", encoding="utf-8")
    home = tmp_path / "home"
    mapping_z = _instructions_mapping(source_z, home / "z" / "Z.md")
    mapping_a = _instructions_mapping(source_a, home / "a" / "A.md")

    plan = build_install_plan((mapping_z, mapping_a), (), False, TIMESTAMP)

    assert tuple(status.path for status in plan.statuses) == (
        mapping_a.destination,
        mapping_z.destination,
    )
    assert plan.changes == (CreateLink(mapping_a), CreateLink(mapping_z))
