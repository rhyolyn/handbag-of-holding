"""Tests for catalog-backed generated skill discovery."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from catalog_fixture import write_catalog
from secret_agents_setup.catalog import load_skill_catalog
from secret_agents_setup.catalog_errors import SkillCatalogError, SkillsDirectoryNotFound


def test_catalog_descriptors_are_canonical_name_sorted_and_target_canonical_sources(tmp_path: Path) -> None:
    write_catalog(tmp_path, "gamma", "alpha", "beta")

    catalog = load_skill_catalog(tmp_path)

    assert [descriptor.name for descriptor in catalog] == ["alpha", "beta", "gamma"]
    assert catalog[0].directory == tmp_path / "work-tracking" / "alpha"
    assert catalog[0].directory.is_relative_to(tmp_path / "work-tracking")


def test_catalog_resolves_a_descriptor_directly_from_its_canonical_source_path(tmp_path: Path) -> None:
    source = tmp_path / "work-tracking" / "alpha"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: alpha\n---\n", encoding="utf-8")
    (tmp_path / "catalog.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "generated": "2026-11-03",
                "entries": [
                    {
                        "name": "alpha",
                        "description": "Use alpha.",
                        "collection": "work-tracking",
                        "source_path": "work-tracking/alpha",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    catalog = load_skill_catalog(tmp_path)

    assert catalog == (catalog[0],)
    assert catalog[0].directory == source


def test_output_is_immutable_tuple(tmp_path: Path) -> None:
    write_catalog(tmp_path, "alpha")

    catalog = load_skill_catalog(tmp_path)

    assert isinstance(catalog, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        catalog[0].name = "changed"  # type: ignore[misc]


def test_missing_skills_directory_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SkillsDirectoryNotFound):
        load_skill_catalog(tmp_path / "missing")


@pytest.mark.parametrize("source_path", ["../alpha", "work-tracking/missing"])
def test_malformed_or_missing_source_path_is_rejected_before_link_planning(tmp_path: Path, source_path: str) -> None:
    write_catalog(tmp_path, "alpha")
    catalog_path = tmp_path / "catalog.json"
    raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    raw["entries"][0]["source_path"] = source_path
    catalog_path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(SkillCatalogError, match="source_path|SKILL.md") as error:
        load_skill_catalog(tmp_path)

    assert str(catalog_path) in str(error.value)
    assert "catalog.py update" in str(error.value)


def test_source_path_name_must_match_the_catalog_canonical_name(tmp_path: Path) -> None:
    write_catalog(tmp_path, "alpha", "beta")
    catalog_path = tmp_path / "catalog.json"
    raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    raw["entries"][0]["source_path"] = "work-tracking/beta"
    catalog_path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(SkillCatalogError, match="source_path must end with canonical name"):
        load_skill_catalog(tmp_path)


def test_windows_drive_prefixed_source_path_is_rejected_before_link_planning(tmp_path: Path) -> None:
    write_catalog(tmp_path, "alpha")
    catalog_path = tmp_path / "catalog.json"
    raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    raw["entries"][0]["source_path"] = "C:../external/alpha"
    catalog_path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(SkillCatalogError, match="canonical collection/name"):
        load_skill_catalog(tmp_path)


def test_missing_canonical_name_has_no_descriptor_or_link_source(tmp_path: Path) -> None:
    write_catalog(tmp_path, "report-receipt")

    catalog = load_skill_catalog(tmp_path)

    assert [descriptor.name for descriptor in catalog] == ["report-receipt"]
    assert all(descriptor.name != "missing-canonical" for descriptor in catalog)
