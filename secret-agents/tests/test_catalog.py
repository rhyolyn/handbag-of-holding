"""Tests for catalog-backed generated skill discovery."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from catalog_fixture import write_catalog
from secret_agents_setup.catalog import load_skill_catalog
from secret_agents_setup.catalog_errors import SkillCatalogError, SkillsDirectoryNotFound


def test_catalog_descriptors_are_canonical_name_sorted_and_target_generated_projection(tmp_path: Path) -> None:
    write_catalog(tmp_path, "gamma", "alpha", "beta")

    catalog = load_skill_catalog(tmp_path)

    assert [descriptor.name for descriptor in catalog] == ["alpha", "beta", "gamma"]
    assert catalog[0].directory == tmp_path / "_generated" / "alpha"
    assert not catalog[0].directory.is_relative_to(tmp_path / "work-tracking")


def test_output_is_immutable_tuple(tmp_path: Path) -> None:
    write_catalog(tmp_path, "alpha")

    catalog = load_skill_catalog(tmp_path)

    assert isinstance(catalog, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        catalog[0].name = "changed"  # type: ignore[misc]


def test_missing_skills_directory_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SkillsDirectoryNotFound):
        load_skill_catalog(tmp_path / "missing")


Mutation = Callable[[dict[str, object]], None]


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda catalog: catalog.pop("generated_projection"), "generated_projection"),
        (lambda catalog: catalog["generated_projection"].pop("alpha"), "alpha"),
        (lambda catalog: catalog["generated_projection"].update({"alpha": "work-tracking/alpha"}), "_generated/alpha"),
    ],
)
def test_malformed_or_missing_projection_mapping_is_rejected_before_link_planning(
    tmp_path: Path, mutate: Mutation, expected: str
) -> None:
    write_catalog(tmp_path, "alpha")
    catalog_path = tmp_path / "catalog.json"
    raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    mutate(raw)
    catalog_path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(SkillCatalogError, match=expected) as error:
        load_skill_catalog(tmp_path)

    assert str(catalog_path) in str(error.value)
    assert "catalog.py update" in str(error.value)


def test_missing_canonical_name_has_no_descriptor_or_link_source(tmp_path: Path) -> None:
    write_catalog(tmp_path, "report-receipt")

    catalog = load_skill_catalog(tmp_path)

    assert [descriptor.name for descriptor in catalog] == ["report-receipt"]
    assert all(descriptor.name != "missing-canonical" for descriptor in catalog)
