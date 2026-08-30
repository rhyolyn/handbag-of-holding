"""Tests for read-only projection classification and install planning."""

from datetime import datetime
from pathlib import Path

from secret_agents_setup.harness_profiles import InstructionsMapping, SkillsMapping
from secret_agents_setup.models import (
    ActionKind,
    FindingState,
    Harness,
    PlannedAction,
    SkillDescriptor,
)
from secret_agents_setup.planning import build_install_plan

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
    projection = _instructions_mapping(source, tmp_path / "home" / ".codex" / "AGENTS.md")

    plan = build_install_plan((projection,), (), False, TIMESTAMP)

    assert plan.can_apply is True
    assert tuple(finding.state for finding in plan.findings) == (FindingState.MISSING,)
    assert plan.actions == (
        PlannedAction(
            kind=ActionKind.CREATE_LINK,
            source=source,
            destination=projection.destination,
            is_directory=False,
        ),
    )


def test_correct_whole_directory_link_needs_no_action(tmp_path: Path) -> None:
    source = tmp_path / "canonical" / "skills"
    source.mkdir(parents=True)
    destination = tmp_path / "home" / ".agents" / "skills"
    destination.parent.mkdir(parents=True)
    destination.symlink_to(source, target_is_directory=True)

    plan = build_install_plan((_skills_mapping(source, destination),), (), False, TIMESTAMP)

    assert tuple(finding.state for finding in plan.findings) == (FindingState.CORRECT,)
    assert plan.actions == ()


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

    plan = build_install_plan((_instructions_mapping(source, destination),), (), False, TIMESTAMP)

    assert tuple(finding.state for finding in plan.findings) == (FindingState.STALE_LINK,)
    assert tuple(action.kind for action in plan.actions) == (ActionKind.REPLACE_LINK,)


def test_broken_link_is_distinguished_and_replaced(tmp_path: Path) -> None:
    source = tmp_path / "canonical" / "AGENTS.md"
    source.parent.mkdir()
    source.write_text("canonical", encoding="utf-8")
    destination = tmp_path / "home" / ".codex" / "AGENTS.md"
    destination.parent.mkdir(parents=True)
    destination.symlink_to(tmp_path / "missing" / "AGENTS.md")

    plan = build_install_plan((_instructions_mapping(source, destination),), (), False, TIMESTAMP)

    assert tuple(finding.state for finding in plan.findings) == (FindingState.BROKEN_LINK,)
    assert tuple(action.kind for action in plan.actions) == (ActionKind.REPLACE_LINK,)


def test_unrelated_instruction_file_blocks_without_backup(tmp_path: Path) -> None:
    source = tmp_path / "canonical" / "AGENTS.md"
    source.parent.mkdir()
    source.write_text("canonical", encoding="utf-8")
    destination = tmp_path / "home" / ".codex" / "AGENTS.md"
    destination.parent.mkdir(parents=True)
    destination.write_text("personal", encoding="utf-8")

    plan = build_install_plan((_instructions_mapping(source, destination),), (), False, TIMESTAMP)

    assert plan.can_apply is False
    assert tuple(finding.state for finding in plan.findings) == (FindingState.UNRELATED,)
    assert plan.findings[0].blocking is True
    assert plan.actions == ()


def test_backup_conflict_names_timestamped_sibling_before_link(tmp_path: Path) -> None:
    source = tmp_path / "canonical" / "AGENTS.md"
    source.parent.mkdir()
    source.write_text("canonical", encoding="utf-8")
    destination = tmp_path / "home" / ".codex" / "AGENTS.md"
    destination.parent.mkdir(parents=True)
    destination.write_text("personal", encoding="utf-8")

    plan = build_install_plan((_instructions_mapping(source, destination),), (), True, TIMESTAMP)

    assert plan.can_apply is True
    assert plan.findings[0].blocking is False
    assert plan.actions == (
        PlannedAction(
            kind=ActionKind.BACKUP,
            source=destination,
            destination=destination.with_name("AGENTS.md.backup-20260829-123456"),
            is_directory=False,
        ),
        PlannedAction(
            kind=ActionKind.CREATE_LINK,
            source=source,
            destination=destination,
            is_directory=False,
        ),
    )


def test_backup_planning_uses_next_free_suffix(tmp_path: Path) -> None:
    source = tmp_path / "canonical" / "AGENTS.md"
    source.parent.mkdir()
    source.write_text("canonical", encoding="utf-8")
    destination = tmp_path / "home" / ".codex" / "AGENTS.md"
    destination.parent.mkdir(parents=True)
    destination.write_text("personal", encoding="utf-8")
    destination.with_name("AGENTS.md.backup-20260829-120000").write_text("occupied", encoding="utf-8")

    plan = build_install_plan(
        (_instructions_mapping(source, destination),),
        (),
        True,
        datetime(2026, 8, 29, 12, 0, 0),
    )

    assert plan.actions[0] == PlannedAction(
        kind=ActionKind.BACKUP,
        source=destination,
        destination=destination.with_name("AGENTS.md.backup-20260829-120000-2"),
        is_directory=False,
    )


def test_real_skill_directory_is_compatible_and_plans_each_missing_skill(
    tmp_path: Path,
) -> None:
    source = tmp_path / "canonical" / "skills"
    source.mkdir(parents=True)
    alpha = _skill(source, "alpha")
    beta = _skill(source, "beta")
    alpha.directory.mkdir()
    beta.directory.mkdir()
    destination = tmp_path / "home" / ".claude" / "skills"
    destination.mkdir(parents=True)
    (destination / "third-party").mkdir()

    plan = build_install_plan((_skills_mapping(source, destination),), (beta, alpha), False, TIMESTAMP)

    assert tuple(finding.state for finding in plan.findings) == (
        FindingState.COMPATIBLE_SKILL_DIRECTORY,
        FindingState.MISSING,
        FindingState.MISSING,
    )
    assert tuple(action.destination.name for action in plan.actions) == ("alpha", "beta")
    assert all(action.kind is ActionKind.CREATE_LINK for action in plan.actions)


def test_correct_per_skill_link_is_preserved(tmp_path: Path) -> None:
    source = tmp_path / "canonical" / "skills"
    source.mkdir(parents=True)
    alpha = _skill(source, "alpha")
    alpha.directory.mkdir()
    destination = tmp_path / "home" / ".claude" / "skills"
    destination.mkdir(parents=True)
    (destination / "alpha").symlink_to(alpha.directory, target_is_directory=True)

    plan = build_install_plan((_skills_mapping(source, destination),), (alpha,), False, TIMESTAMP)

    assert tuple(finding.state for finding in plan.findings) == (
        FindingState.COMPATIBLE_SKILL_DIRECTORY,
        FindingState.CORRECT,
    )
    assert plan.actions == ()


def test_same_name_skill_collision_blocks_entire_plan(tmp_path: Path) -> None:
    source = tmp_path / "canonical" / "skills"
    source.mkdir(parents=True)
    alpha = _skill(source, "alpha")
    alpha.directory.mkdir()
    destination = tmp_path / "home" / ".claude" / "skills"
    destination.mkdir(parents=True)
    (destination / "alpha").mkdir()
    guidance_source = tmp_path / "canonical" / "AGENTS.md"
    guidance_source.write_text("guidance", encoding="utf-8")
    missing_instructions = _instructions_mapping(guidance_source, tmp_path / "home" / ".codex" / "AGENTS.md")

    plan = build_install_plan(
        (_skills_mapping(source, destination), missing_instructions),
        (alpha,),
        False,
        TIMESTAMP,
    )

    assert plan.can_apply is False
    assert FindingState.SKILL_NAME_COLLISION in {finding.state for finding in plan.findings}
    assert plan.actions == ()


def test_findings_and_actions_have_stable_path_order(tmp_path: Path) -> None:
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

    assert tuple(finding.path for finding in plan.findings) == (
        mapping_a.destination,
        mapping_z.destination,
    )
    assert tuple(action.destination for action in plan.actions) == (
        mapping_a.destination,
        mapping_z.destination,
    )
