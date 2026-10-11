"""Unit tests for the SkillCatalog stdlib program."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
CATALOG_SCRIPT = ROOT / "skills" / "query-all-skills" / "scripts" / "catalog.py"


def _load_catalog() -> ModuleType:
    spec = importlib.util.spec_from_file_location("catalog", CATALOG_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["catalog"] = module
    spec.loader.exec_module(module)
    return module


catalog = _load_catalog()


def _skill_text(
    name: str,
    category: str = "Testing",
    short: str = "ttest",
    updated: str = "2026-10-10",
    aliases: str = "",
    description: str = "Use when testing.",
) -> str:
    alias_part = f" · **Aliases:** {aliases}" if aliases else ""
    return (
        f"---\nname: {name}\ndescription: {description}\n---\n\n"
        f"# {name.replace('-', ' ').title()}\n\n"
        f"**Category:** {category} · **Short:** {short} · "
        f"**Updated:** {updated}{alias_part}\n\nBody text.\n"
    )


def test_parse_frontmatter_returns_name_and_description() -> None:
    text = "---\nname: my-skill\ndescription: Use when testing.\n---\n\n# Body\n"
    result = catalog.parse_frontmatter(text)
    assert result["name"] == "my-skill"
    assert result["description"] == "Use when testing."


def test_parse_frontmatter_raises_on_missing_delimiter() -> None:
    import pytest
    with pytest.raises(catalog.MissingFrontmatter):
        catalog.parse_frontmatter("# No frontmatter\n")


def test_parse_skill_header_parses_all_fields() -> None:
    text = _skill_text("run-unit-tests", "Testing", "trut", "2026-10-10", "rut")
    h = catalog.parse_skill_header(text)
    assert h.category == "Testing"
    assert h.shorthand == "trut"
    assert h.updated == "2026-10-10"
    assert h.aliases == ("rut",)


def test_parse_skill_header_omits_aliases_when_absent() -> None:
    text = _skill_text("agent-plan", "Agent Workflow", "ap")
    h = catalog.parse_skill_header(text)
    assert h.aliases == ()


def test_parse_skill_header_raises_when_missing() -> None:
    import pytest
    text = "---\nname: x\ndescription: y\n---\n\n# X\n\nNo header line.\n"
    with pytest.raises(catalog.MissingSkillHeader):
        catalog.parse_skill_header(text)


def test_extract_h1_returns_heading_text() -> None:
    text = "---\nname: x\ndescription: y\n---\n\n# My Skill\n\nBody.\n"
    assert catalog.extract_h1(text) == "My Skill"


def test_extract_h1_raises_when_missing() -> None:
    import pytest
    with pytest.raises(catalog.MissingDisplayName):
        catalog.extract_h1("---\nname: x\n---\nNo heading.\n")
