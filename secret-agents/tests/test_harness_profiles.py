"""Mapping contracts verified against first-party docs on 2026-08-28.

These tests prove deterministic mapping behavior, not harness consumption.
"""

from pathlib import Path

import pytest

from secret_agents_setup.harness_profiles import (
    InstallMapping,
    InstructionsMapping,
    SkillsMapping,
    build_install_mappings,
)
from secret_agents_setup.models import AgentRoot, Harness


@pytest.fixture
def agent_root(tmp_path: Path) -> AgentRoot:
    root = tmp_path / "canonical"
    return AgentRoot(path=root, schema_version=1, identity="handbag-secret-agents")


def test_codex_mappings_name_instructions_and_skills(agent_root: AgentRoot, tmp_path: Path) -> None:
    home = tmp_path / "home"

    mappings = build_install_mappings(agent_root, home, (Harness.CODEX,))

    assert mappings == (
        SkillsMapping((Harness.CODEX,), agent_root.path / "skills", home / ".agents" / "skills"),
        InstructionsMapping((Harness.CODEX,), agent_root.path / "AGENTS.md", home / ".codex" / "AGENTS.md"),
    )


def test_claude_mappings_name_instructions_and_skills(agent_root: AgentRoot, tmp_path: Path) -> None:
    home = tmp_path / "home"

    mappings = build_install_mappings(agent_root, home, (Harness.CLAUDE,))

    assert mappings == (
        InstructionsMapping((Harness.CLAUDE,), agent_root.path / "AGENTS.md", home / ".claude" / "CLAUDE.md"),
        SkillsMapping((Harness.CLAUDE,), agent_root.path / "skills", home / ".claude" / "skills"),
    )


def test_copilot_mappings_name_instructions_and_skills(agent_root: AgentRoot, tmp_path: Path) -> None:
    home = tmp_path / "home"

    mappings = build_install_mappings(agent_root, home, (Harness.COPILOT,))

    assert mappings == (
        SkillsMapping((Harness.COPILOT,), agent_root.path / "skills", home / ".agents" / "skills"),
        InstructionsMapping(
            (Harness.COPILOT,),
            agent_root.path / "AGENTS.md",
            home / ".copilot" / "copilot-instructions.md",
        ),
    )


def test_all_deduplicates_shared_skills_and_orders_destinations(agent_root: AgentRoot, tmp_path: Path) -> None:
    home = tmp_path / "home"

    mappings = build_install_mappings(agent_root, home, (Harness.ALL,))

    assert tuple(mapping.destination.relative_to(home).as_posix() for mapping in mappings) == (
        ".agents/skills",
        ".claude/CLAUDE.md",
        ".claude/skills",
        ".codex/AGENTS.md",
        ".copilot/copilot-instructions.md",
    )


def test_shared_skills_mapping_merges_codex_and_copilot(agent_root: AgentRoot, tmp_path: Path) -> None:
    home = tmp_path / "home"

    mappings = build_install_mappings(agent_root, home, (Harness.ALL,))
    shared = next(mapping for mapping in mappings if mapping.destination == home / ".agents" / "skills")

    assert isinstance(shared, SkillsMapping)
    assert shared.harnesses == (Harness.CODEX, Harness.COPILOT)


def test_explicit_codex_and_copilot_selection_deduplicates_shared_skills(agent_root: AgentRoot, tmp_path: Path) -> None:
    mappings = build_install_mappings(
        agent_root,
        tmp_path / "home",
        (Harness.COPILOT, Harness.CODEX),
    )

    shared = tuple(mapping for mapping in mappings if mapping.destination.parts[-2:] == (".agents", "skills"))
    assert len(shared) == 1
    assert isinstance(shared[0], SkillsMapping)
    assert shared[0].harnesses == (Harness.CODEX, Harness.COPILOT)


def test_all_instructions_mappings_share_canonical_agents_source(agent_root: AgentRoot, tmp_path: Path) -> None:
    mappings = build_install_mappings(agent_root, tmp_path / "home", (Harness.ALL,))

    instructions_sources = {mapping.source for mapping in mappings if isinstance(mapping, InstructionsMapping)}
    assert instructions_sources == {agent_root.path / "AGENTS.md"}


def test_install_mapping_union_covers_both_concrete_types() -> None:
    assert InstallMapping == InstructionsMapping | SkillsMapping
