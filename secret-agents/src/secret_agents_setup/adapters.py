"""Harness-specific projection mappings."""

from __future__ import annotations

from pathlib import Path

from .models import AgentRoot, Harness, Projection, ProjectionKind

_HARNESS_ORDER = (Harness.CODEX, Harness.CLAUDE, Harness.COPILOT)
_PROJECTION_SPECS: dict[Harness, tuple[tuple[ProjectionKind, str, str, bool], ...]] = {
    Harness.CODEX: (
        (ProjectionKind.SKILLS, "skills", ".agents/skills", True),
        (ProjectionKind.GUIDANCE, "AGENTS.md", ".codex/AGENTS.md", False),
    ),
    Harness.CLAUDE: (
        (ProjectionKind.SKILLS, "skills", ".claude/skills", True),
        (ProjectionKind.GUIDANCE, "AGENTS.md", ".claude/CLAUDE.md", False),
    ),
    Harness.COPILOT: (
        (ProjectionKind.SKILLS, "skills", ".agents/skills", True),
        (
            ProjectionKind.GUIDANCE,
            "AGENTS.md",
            ".copilot/copilot-instructions.md",
            False,
        ),
    ),
}


def build_projections(
    root: AgentRoot, home: Path, harnesses: tuple[Harness, ...]
) -> tuple[Projection, ...]:
    """Build deterministic, destination-deduplicated harness projections."""
    selected = _selected_harnesses(harnesses)
    projections: dict[Path, Projection] = {}

    for harness in selected:
        for kind, source_name, destination_name, is_directory in _PROJECTION_SPECS[harness]:
            destination = home / Path(destination_name)
            existing = projections.get(destination)
            if existing is not None:
                projections[destination] = Projection(
                    harnesses=(*existing.harnesses, harness),
                    kind=existing.kind,
                    source=existing.source,
                    destination=destination,
                    is_directory=existing.is_directory,
                )
                continue
            projections[destination] = Projection(
                harnesses=(harness,),
                kind=kind,
                source=root.path / source_name,
                destination=destination,
                is_directory=is_directory,
            )

    ordered_destinations = sorted(projections, key=lambda item: item.as_posix())
    return tuple(projections[path] for path in ordered_destinations)


def _selected_harnesses(harnesses: tuple[Harness, ...]) -> tuple[Harness, ...]:
    if Harness.ALL in harnesses:
        return _HARNESS_ORDER
    return tuple(harness for harness in _HARNESS_ORDER if harness in harnesses)
