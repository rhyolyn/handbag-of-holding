"""Skill discovery and minimal standard-library frontmatter validation."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .catalog_errors import (
    DuplicateSkillNames,
    InvalidSkillName,
    MissingFrontmatter,
    MissingSkillDescription,
    MissingSkillFile,
    MissingSkillName,
    SkillDirectoryNameMismatch,
    SkillsDirectoryNotFound,
    UnterminatedFrontmatter,
)
from .catalog_errors import SkillCatalogError as SkillCatalogError
from .models import SkillDescriptor

NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_RECOGNIZED_FIELDS = ("name", "description")


def load_skill_catalog(skills_root: Path) -> tuple[SkillDescriptor, ...]:
    if not skills_root.is_dir():
        raise SkillsDirectoryNotFound(skills_root)

    parsed: list[tuple[Path, str, str]] = []
    for directory in sorted(child for child in skills_root.iterdir() if child.is_dir()):
        name, description = _parse_skill(directory)
        parsed.append((directory, name, description))

    _reject_duplicate_names(parsed)

    descriptors: list[SkillDescriptor] = []
    for directory, name, description in parsed:
        if name != directory.name:
            raise SkillDirectoryNameMismatch(directory, name)
        descriptors.append(SkillDescriptor(name, description, directory))
    return tuple(descriptors)


def _parse_skill(directory: Path) -> tuple[str, str]:
    skill_md = directory / "SKILL.md"
    if not skill_md.is_file():
        raise MissingSkillFile(directory)

    fields = _parse_frontmatter(skill_md)
    name = fields.get("name")
    if name is None:
        raise MissingSkillName(skill_md)
    description = fields.get("description")
    if description is None:
        raise MissingSkillDescription(skill_md)
    if not NAME_PATTERN.fullmatch(name):
        raise InvalidSkillName(skill_md, name)
    return name, description


def _parse_frontmatter(skill_md: Path) -> dict[str, str]:
    lines = skill_md.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise MissingFrontmatter(skill_md)

    fields: dict[str, str] = {}
    closed = False
    for line in lines[1:]:
        if line.strip() == "---":
            closed = True
            break
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        if key in _RECOGNIZED_FIELDS:
            fields[key] = _strip_matching_quotes(raw_value.strip())

    if not closed:
        raise UnterminatedFrontmatter(skill_md)
    return fields


def _strip_matching_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _reject_duplicate_names(parsed: list[tuple[Path, str, str]]) -> None:
    counts = Counter(name for _, name, _ in parsed)
    duplicates = sorted(name for name, count in counts.items() if count > 1)
    if duplicates:
        raise DuplicateSkillNames(duplicates)
