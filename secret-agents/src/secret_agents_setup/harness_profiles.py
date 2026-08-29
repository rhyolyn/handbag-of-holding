"""Per-harness profiles: the single home for everything that varies by harness.

A ``HarnessProfile`` gathers the harness-specific facts and behaviors that the
rest of the toolchain — and the skills it projects — must not hard-code inline.
Today a profile carries only projection specs. Cost models, model
recommendations, and invocation conventions are the intended next facets: add a
field here rather than branching on ``Harness`` in skills or planning code.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import NamedTuple

from .models import AgentRoot, Harness, Projection, ProjectionKind


class _ProjectionSpec(NamedTuple):
    kind: ProjectionKind
    source_name: str
    destination_name: str
    is_directory: bool


@dataclass(frozen=True)
class HarnessProfile:
    """Everything that varies by harness. Projections are the first facet."""

    projections: tuple[_ProjectionSpec, ...]


_HARNESS_ORDER = (Harness.CODEX, Harness.CLAUDE, Harness.COPILOT)
_PROFILES: dict[Harness, HarnessProfile] = {
    Harness.CODEX: HarnessProfile(
        projections=(
            _ProjectionSpec(ProjectionKind.SKILLS, "skills", ".agents/skills", True),
            _ProjectionSpec(ProjectionKind.GUIDANCE, "AGENTS.md", ".codex/AGENTS.md", False),
        ),
    ),
    Harness.CLAUDE: HarnessProfile(
        projections=(
            _ProjectionSpec(ProjectionKind.SKILLS, "skills", ".claude/skills", True),
            _ProjectionSpec(ProjectionKind.GUIDANCE, "AGENTS.md", ".claude/CLAUDE.md", False),
        ),
    ),
    Harness.COPILOT: HarnessProfile(
        projections=(
            _ProjectionSpec(ProjectionKind.SKILLS, "skills", ".agents/skills", True),
            _ProjectionSpec(ProjectionKind.GUIDANCE, "AGENTS.md", ".copilot/copilot-instructions.md", False),
        ),
    ),
}


def build_projections(root: AgentRoot, home: Path, harnesses: tuple[Harness, ...]) -> tuple[Projection, ...]:
    """Build deterministic, destination-deduplicated harness projections."""
    projections: dict[Path, Projection] = {}
    for harness, spec in _selected_specs(harnesses):
        destination = home / spec.destination_name
        existing = projections.get(destination)
        if existing is None:
            projections[destination] = Projection(
                harnesses=(harness,),
                kind=spec.kind,
                source=root.path / spec.source_name,
                destination=destination,
                is_directory=spec.is_directory,
            )
        else:
            projections[destination] = replace(existing, harnesses=(*existing.harnesses, harness))
    return tuple(projections[path] for path in sorted(projections, key=Path.as_posix))


def _selected_specs(harnesses: tuple[Harness, ...]) -> Iterator[tuple[Harness, _ProjectionSpec]]:
    for harness in _selected_harnesses(harnesses):
        for spec in _PROFILES[harness].projections:
            yield harness, spec


def _selected_harnesses(harnesses: tuple[Harness, ...]) -> tuple[Harness, ...]:
    if Harness.ALL in harnesses:
        return _HARNESS_ORDER
    return tuple(harness for harness in _HARNESS_ORDER if harness in harnesses)
