"""Tests for skill discovery and minimal frontmatter validation."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from secret_agents_setup.catalog import SkillCatalogError, load_skill_catalog


def write_skill(
    skills_root: Path,
    dir_name: str,
    *,
    name: str | None = None,
    description: str = "Use when testing this skill.",
    frontmatter: str | None = None,
) -> Path:
    directory = skills_root / dir_name
    directory.mkdir(parents=True, exist_ok=True)
    if frontmatter is None:
        declared = dir_name if name is None else name
        frontmatter = f"---\nname: {declared}\ndescription: {description}\n---\n"
    (directory / "SKILL.md").write_text(frontmatter + "\n# Body\n", encoding="utf-8")
    return directory


def test_discovery_is_sorted(tmp_path: Path) -> None:
    for dir_name in ("gamma", "alpha", "beta"):
        write_skill(tmp_path, dir_name)
    catalog = load_skill_catalog(tmp_path)
    assert [descriptor.name for descriptor in catalog] == ["alpha", "beta", "gamma"]
    assert catalog[0].directory == tmp_path / "alpha"


def test_output_is_immutable_tuple(tmp_path: Path) -> None:
    write_skill(tmp_path, "alpha")
    catalog = load_skill_catalog(tmp_path)
    assert isinstance(catalog, tuple)
    frozen_attribute = "name"
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(catalog[0], frozen_attribute, "changed")


def test_missing_skill_md_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "alpha").mkdir()
    with pytest.raises(SkillCatalogError):
        load_skill_catalog(tmp_path)


def test_missing_frontmatter_delimiters_is_rejected(tmp_path: Path) -> None:
    directory = tmp_path / "alpha"
    directory.mkdir()
    (directory / "SKILL.md").write_text("# no frontmatter here\n", encoding="utf-8")
    with pytest.raises(SkillCatalogError):
        load_skill_catalog(tmp_path)


def test_missing_name_is_rejected(tmp_path: Path) -> None:
    write_skill(tmp_path, "alpha", frontmatter="---\ndescription: Use when testing.\n---\n")
    with pytest.raises(SkillCatalogError):
        load_skill_catalog(tmp_path)


def test_missing_description_is_rejected(tmp_path: Path) -> None:
    write_skill(tmp_path, "alpha", frontmatter="---\nname: alpha\n---\n")
    with pytest.raises(SkillCatalogError):
        load_skill_catalog(tmp_path)


def test_directory_name_mismatch_is_rejected(tmp_path: Path) -> None:
    write_skill(tmp_path, "alpha", name="beta")
    with pytest.raises(SkillCatalogError):
        load_skill_catalog(tmp_path)


def test_duplicate_declared_names_are_rejected(tmp_path: Path) -> None:
    write_skill(tmp_path, "one", name="dup")
    write_skill(tmp_path, "two", name="dup")
    with pytest.raises(SkillCatalogError):
        load_skill_catalog(tmp_path)


def test_description_value_may_contain_colons(tmp_path: Path) -> None:
    write_skill(
        tmp_path,
        "gate",
        frontmatter="---\nname: gate\ndescription: Runs a gate: first lint, then tests\n---\n",
    )
    catalog = load_skill_catalog(tmp_path)
    assert catalog[0].description == "Runs a gate: first lint, then tests"


def test_quoted_description_preserves_inner_colon(tmp_path: Path) -> None:
    write_skill(
        tmp_path,
        "gate",
        frontmatter='---\nname: gate\ndescription: "Runs a gate: first lint"\n---\n',
    )
    catalog = load_skill_catalog(tmp_path)
    assert catalog[0].description == "Runs a gate: first lint"
