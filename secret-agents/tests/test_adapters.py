"""Projection contracts verified against first-party docs on 2026-08-28.

These tests prove deterministic projection behavior, not harness consumption.
"""

from pathlib import Path

import pytest

from secret_agents_setup.adapters import build_projections
from secret_agents_setup.models import AgentRoot, Harness, ProjectionKind


@pytest.fixture
def agent_root(tmp_path: Path) -> AgentRoot:
    root = tmp_path / "canonical"
    return AgentRoot(path=root, schema_version=1, identity="handbag-secret-agents")


@pytest.mark.parametrize(
    ("harness", "expected"),
    [
        (
            Harness.CODEX,
            (
                (".agents/skills", ProjectionKind.SKILLS, "skills", True),
                (".codex/AGENTS.md", ProjectionKind.GUIDANCE, "AGENTS.md", False),
            ),
        ),
        (
            Harness.CLAUDE,
            (
                (".claude/CLAUDE.md", ProjectionKind.GUIDANCE, "AGENTS.md", False),
                (".claude/skills", ProjectionKind.SKILLS, "skills", True),
            ),
        ),
        (
            Harness.COPILOT,
            (
                (".agents/skills", ProjectionKind.SKILLS, "skills", True),
                (
                    ".copilot/copilot-instructions.md",
                    ProjectionKind.GUIDANCE,
                    "AGENTS.md",
                    False,
                ),
            ),
        ),
    ],
)
def test_harness_uses_verified_projection_paths(
    agent_root: AgentRoot,
    tmp_path: Path,
    harness: Harness,
    expected: tuple[tuple[str, ProjectionKind, str, bool], ...],
) -> None:
    home = tmp_path / "home"

    projections = build_projections(agent_root, home, (harness,))

    assert (
        tuple(
            (
                projection.destination.relative_to(home).as_posix(),
                projection.kind,
                projection.source.relative_to(agent_root.path).as_posix(),
                projection.is_directory,
            )
            for projection in projections
        )
        == expected
    )
    assert all(projection.harnesses == (harness,) for projection in projections)


def test_all_deduplicates_shared_skills_and_orders_destinations(
    agent_root: AgentRoot, tmp_path: Path
) -> None:
    home = tmp_path / "home"

    projections = build_projections(agent_root, home, (Harness.ALL,))

    assert tuple(
        projection.destination.relative_to(home).as_posix() for projection in projections
    ) == (
        ".agents/skills",
        ".claude/CLAUDE.md",
        ".claude/skills",
        ".codex/AGENTS.md",
        ".copilot/copilot-instructions.md",
    )
    shared_skills = projections[0]
    assert shared_skills.harnesses == (Harness.CODEX, Harness.COPILOT)


def test_explicit_codex_and_copilot_selection_deduplicates_shared_skills(
    agent_root: AgentRoot, tmp_path: Path
) -> None:
    projections = build_projections(
        agent_root,
        tmp_path / "home",
        (Harness.COPILOT, Harness.CODEX),
    )

    shared = tuple(
        projection
        for projection in projections
        if projection.destination.parts[-2:] == (".agents", "skills")
    )
    assert len(shared) == 1
    assert shared[0].harnesses == (Harness.CODEX, Harness.COPILOT)


def test_all_guidance_projections_share_canonical_agents_source(
    agent_root: AgentRoot, tmp_path: Path
) -> None:
    projections = build_projections(agent_root, tmp_path / "home", (Harness.ALL,))

    guidance_sources = {
        projection.source
        for projection in projections
        if projection.kind is ProjectionKind.GUIDANCE
    }
    assert guidance_sources == {agent_root.path / "AGENTS.md"}
