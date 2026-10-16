"""Behavioral tests for the skills README renderer and drift guard."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent
README_PATH = ROOT / "skills" / "README.md"
SCRIPT_PATH = ROOT / "skills" / "skill-authoring" / "update-skills-readme" / "scripts" / "render_html.py"


def _load_renderer() -> ModuleType:
    spec = importlib.util.spec_from_file_location("render_html", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_verify_accepts_the_documented_skill_catalog() -> None:
    renderer = _load_renderer()
    skill_names = renderer.skill_directories(ROOT / "skills")

    assert renderer.verify(README_PATH.read_text(encoding="utf-8"), skill_names) == []


def test_verify_reports_missing_catalog_entries_and_dead_anchors() -> None:
    renderer = _load_renderer()
    markdown = "# Skills\n\n- [alpha](#alpha)\n- [broken](#missing)\n\n### alpha\n"

    assert renderer.verify(markdown, ["alpha", "bravo"]) == [
        "missing section heading: ### bravo",
        "missing TOC/inventory link: #bravo",
        "dead anchor: #missing",
    ]


def test_skill_directories_inventory_only_manifest_catalog_canonical_sources(tmp_path: Path) -> None:
    renderer = _load_renderer()
    skills_root = tmp_path / "skills"
    (skills_root / "agent-workflow" / "alpha").mkdir(parents=True)
    (skills_root / "agent-workflow" / "alpha" / "SKILL.md").write_text("# Alpha\n", encoding="utf-8")
    (skills_root / "_generated" / "alpha").mkdir(parents=True)
    (skills_root / "_generated" / "alpha" / "SKILL.md").write_text("# Generated Alpha\n", encoding="utf-8")
    (skills_root / "not-a-collection" / "leaked").mkdir(parents=True)
    (skills_root / "not-a-collection" / "leaked" / "SKILL.md").write_text("# Leaked\n", encoding="utf-8")
    (skills_root / "collections.json").write_text(
        json.dumps({"schema_version": 1, "source_layout": "collections", "collections": [{"name": "agent-workflow"}]}),
        encoding="utf-8",
    )
    (skills_root / "catalog.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "entries": [{"name": "alpha", "collection": "agent-workflow", "source_path": "agent-workflow/alpha"}],
            }
        ),
        encoding="utf-8",
    )

    assert renderer.skill_directories(skills_root) == ["alpha"]


def test_skill_directories_refuse_catalog_source_outside_declared_collection(tmp_path: Path) -> None:
    renderer = _load_renderer()
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    (skills_root / "collections.json").write_text(
        json.dumps({"schema_version": 1, "source_layout": "collections", "collections": [{"name": "agent-workflow"}]}),
        encoding="utf-8",
    )
    (skills_root / "catalog.json").write_text(
        json.dumps(
            {"schema_version": 2, "entries": [{"name": "alpha", "collection": "other", "source_path": "other/alpha"}]}
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"catalog entry 'alpha'.*other/alpha.*declared collection"):
        renderer.skill_directories(skills_root)


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ({"name": "alpha", "collection": "agent-workflow", "source_path": "agent-workflow/beta"}, "does not match"),
        ({"name": "alpha", "collection": "other", "source_path": "agent-workflow/alpha"}, "collection"),
    ],
)
def test_skill_directories_refuse_contradictory_catalog_identity(
    tmp_path: Path, entry: dict[str, str], message: str
) -> None:
    renderer = _load_renderer()
    skills_root = tmp_path / "skills"
    for name in ("alpha", "beta"):
        (skills_root / "agent-workflow" / name).mkdir(parents=True)
        (skills_root / "agent-workflow" / name / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    (skills_root / "collections.json").write_text(
        json.dumps({"schema_version": 1, "source_layout": "collections", "collections": [{"name": "agent-workflow"}]}),
        encoding="utf-8",
    )
    (skills_root / "catalog.json").write_text(json.dumps({"schema_version": 2, "entries": [entry]}), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        renderer.skill_directories(skills_root)


def test_verify_inventory_requires_only_canonical_catalog_names() -> None:
    renderer = _load_renderer()
    markdown = "# Skills\n\n- [alpha](#alpha)\n\n### alpha\n"

    assert renderer.verify(markdown, ["alpha"]) == []
