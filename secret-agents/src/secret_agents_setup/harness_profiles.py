"""Per-harness profiles: the single home for everything that varies by harness.

A ``HarnessProfile`` gathers the harness-specific facts and behaviors that the
rest of the toolchain — and the skills it maps — must not hard-code inline.
Today a profile carries only mapping specs. Cost models, model recommendations,
and invocation conventions are the intended next facets: add a field here rather
than branching on ``Harness`` in skills or planning code.

An ``InstructionsMapping`` links the canonical ``AGENTS.md`` to a harness
instruction file. A ``SkillsMapping`` links the canonical skills collection to a
harness skills directory. The concrete mapping type — not a ``kind`` field —
determines file-versus-directory behavior throughout planning and execution.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import NamedTuple

from .models import AgentRoot, Harness


@dataclass(frozen=True)
class InstructionsMapping:
    """The canonical ``AGENTS.md`` linked to a harness instruction file."""

    harnesses: tuple[Harness, ...]
    source: Path
    destination: Path


@dataclass(frozen=True)
class SkillsMapping:
    """The canonical skills collection linked to a harness skills directory."""

    harnesses: tuple[Harness, ...]
    source: Path
    destination: Path


InstallMapping = InstructionsMapping | SkillsMapping


class _MappingSpec(NamedTuple):
    is_skills: bool
    source_name: str
    destination_name: str


@dataclass(frozen=True)
class HarnessProfile:
    """Everything that varies by harness. Mappings are the first facet."""

    mappings: tuple[_MappingSpec, ...]


_HARNESS_ORDER = (Harness.CODEX, Harness.CLAUDE, Harness.COPILOT)
_PROFILES: dict[Harness, HarnessProfile] = {
    Harness.CODEX: HarnessProfile(
        mappings=(
            _MappingSpec(True, "skills", ".agents/skills"),
            _MappingSpec(False, "AGENTS.md", ".codex/AGENTS.md"),
        ),
    ),
    Harness.CLAUDE: HarnessProfile(
        mappings=(
            _MappingSpec(True, "skills", ".claude/skills"),
            _MappingSpec(False, "AGENTS.md", ".claude/CLAUDE.md"),
        ),
    ),
    Harness.COPILOT: HarnessProfile(
        mappings=(
            _MappingSpec(True, "skills", ".agents/skills"),
            _MappingSpec(False, "AGENTS.md", ".copilot/copilot-instructions.md"),
        ),
    ),
}


def build_install_mappings(root: AgentRoot, home: Path, harnesses: tuple[Harness, ...]) -> tuple[InstallMapping, ...]:
    """Build deterministic, destination-deduplicated harness install mappings."""
    mappings: dict[Path, InstallMapping] = {}
    for harness, spec in _selected_specs(harnesses):
        destination = home / spec.destination_name
        existing = mappings.get(destination)
        if existing is None:
            mappings[destination] = _build_mapping(spec, (harness,), root.path / spec.source_name, destination)
        else:
            mappings[destination] = replace(existing, harnesses=(*existing.harnesses, harness))
    return tuple(mappings[path] for path in sorted(mappings, key=Path.as_posix))


def _build_mapping(
    spec: _MappingSpec,
    harnesses: tuple[Harness, ...],
    source: Path,
    destination: Path,
) -> InstallMapping:
    if spec.is_skills:
        return SkillsMapping(harnesses=harnesses, source=source, destination=destination)
    return InstructionsMapping(harnesses=harnesses, source=source, destination=destination)


def _selected_specs(harnesses: tuple[Harness, ...]) -> Iterator[tuple[Harness, _MappingSpec]]:
    for harness in _selected_harnesses(harnesses):
        for spec in _PROFILES[harness].mappings:
            yield harness, spec


def _selected_harnesses(harnesses: tuple[Harness, ...]) -> tuple[Harness, ...]:
    if Harness.ALL in harnesses:
        return _HARNESS_ORDER
    return tuple(harness for harness in _HARNESS_ORDER if harness in harnesses)
