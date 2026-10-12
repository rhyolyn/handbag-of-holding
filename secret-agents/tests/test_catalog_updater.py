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


import dataclasses
import json


def _write_skill(root: Path, name: str, text: str) -> Path:
    d = root / name
    d.mkdir(exist_ok=True)
    (d / "SKILL.md").write_text(text, encoding="utf-8")
    return d


def test_scan_canonical_dirs_excludes_generated_aliases(tmp_path: Path) -> None:
    (tmp_path / "my-skill").mkdir()
    (tmp_path / "my-skill" / "SKILL.md").write_text(
        _skill_text("my-skill", "Testing", "tms"), encoding="utf-8"
    )
    (tmp_path / "tms").mkdir()
    (tmp_path / "tms" / "SKILL.md").write_text(
        "---\nname: tms\ndescription: Alias.\n---\n\n<!-- generated:my-skill:2026-10-10 -->\n",
        encoding="utf-8",
    )
    sc = catalog.SkillCatalog(tmp_path)
    result = sc._scan_canonical_dirs()
    assert len(result) == 1
    assert result[0].name == "my-skill"


def test_scan_canonical_dirs_raises_on_missing_skill_file(tmp_path: Path) -> None:
    import pytest
    (tmp_path / "bad-skill").mkdir()
    sc = catalog.SkillCatalog(tmp_path)
    with pytest.raises(catalog.CatalogError):
        sc._scan_canonical_dirs()


def test_canonical_entry_from_dir_returns_correct_fields(tmp_path: Path) -> None:
    (tmp_path / "run-unit-tests").mkdir()
    (tmp_path / "run-unit-tests" / "SKILL.md").write_text(
        _skill_text("run-unit-tests", "Testing", "trut", aliases="rut"),
        encoding="utf-8",
    )
    entry = catalog.CanonicalEntry.from_dir(tmp_path / "run-unit-tests", "2026-10-10")
    assert entry.name == "run-unit-tests"
    assert entry.category == "Testing"
    assert entry.shorthand == "trut"
    assert entry.aliases == ("rut",)
    assert len(entry.semantic_hash) == 64
    assert len(entry.content_hash) == 64


def test_stat_cache_miss_on_missing_file(tmp_path: Path) -> None:
    result = catalog.StatCache.load(tmp_path / "nonexistent.json", tmp_path)
    assert result is None


def test_stat_cache_roundtrip(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.json"
    cache = catalog.StatCache(
        schema_version=catalog.CACHE_SCHEMA_VERSION,
        agent_root=str(tmp_path),
        catalog_hash="abc123",
        entries={"x/SKILL.md": catalog.StatEntry(size=100, mtime_ns=123456789)},
    )
    cache.save(cache_path)
    loaded = catalog.StatCache.load(cache_path, tmp_path)
    assert loaded is not None
    assert loaded.catalog_hash == "abc123"
    assert loaded.entries["x/SKILL.md"].size == 100


def test_stat_entry_from_path(tmp_path: Path) -> None:
    skill_dir = tmp_path / "x"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("content", encoding="utf-8")
    entry = catalog.StatEntry.from_path(skill_dir)
    assert entry.size > 0
    assert entry.mtime_ns > 0


def test_show_fast_path_reads_no_skill_bodies(tmp_path: Path) -> None:
    """Warm-cache show must not read any SKILL.md body."""
    import io, unittest.mock

    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(_skill_text("my-skill", "Testing", "tms"), encoding="utf-8")

    toc_text = "# Skills\n\nGenerated 2026-10-10.\n"
    (tmp_path / catalog.TOC_FILENAME).write_text(toc_text, encoding="utf-8")

    entry = catalog.CanonicalEntry.from_dir(skill_dir, "2026-10-10")
    catalog_data = {
        "schema_version": catalog.SCHEMA_VERSION,
        "generated": "2026-10-10",
        "entries": [dataclasses.asdict(entry)],
        "generated_aliases": {},
    }
    catalog_json_text = json.dumps(catalog_data)
    (tmp_path / catalog.CATALOG_FILENAME).write_text(catalog_json_text, encoding="utf-8")

    stat_entry = catalog.StatEntry.from_path(skill_dir)
    cache = catalog.StatCache(
        schema_version=catalog.CACHE_SCHEMA_VERSION,
        agent_root=str(tmp_path),
        catalog_hash=catalog.compute_content_hash(catalog_json_text),
        entries={"my-skill/SKILL.md": stat_entry},
    )
    cache_path = tmp_path / "cache.json"
    cache.save(cache_path)

    read_calls: list[str] = []
    original_read = Path.read_text

    def spy(self: Path, **kwargs):  # type: ignore[no-untyped-def]
        if self.name == "SKILL.md":
            read_calls.append(str(self))
        return original_read(self, **kwargs)

    sc = catalog.SkillCatalog(tmp_path, cache_path=cache_path)
    with unittest.mock.patch.object(Path, "read_text", spy):
        sc.show(out=io.StringIO())

    assert read_calls == [], f"Fast path read SKILL.md bodies: {read_calls}"


def test_semantic_hash_ignores_updated_date() -> None:
    text_a = _skill_text("x", updated="2026-01-01")
    text_b = _skill_text("x", updated="2026-12-31")
    assert catalog.compute_semantic_hash(text_a) == catalog.compute_semantic_hash(text_b)


def test_semantic_hash_differs_on_content_change() -> None:
    text_a = _skill_text("x", description="Use when foo.")
    text_b = _skill_text("x", description="Use when bar.")
    assert catalog.compute_semantic_hash(text_a) != catalog.compute_semantic_hash(text_b)


def test_with_updated_returns_new_entry(tmp_path: Path) -> None:
    text = _skill_text("my-skill", updated="2026-01-01")
    entry = catalog.CanonicalEntry.from_dir(
        _write_skill(tmp_path, "my-skill", text), "2026-01-01"
    )
    bumped = entry.with_updated("2026-10-10")
    assert bumped.updated == "2026-10-10"
    assert bumped.name == entry.name


def test_catalog_build_generates_alias_map() -> None:
    entry = catalog.CanonicalEntry(
        "run-unit-tests", "Run Unit Tests", "Run tests.", "Testing",
        "trut", ("rut",), "2026-10-10", "h1", "h2",
    )
    c = catalog.Catalog.build([entry], "2026-10-10")
    assert c.generated_aliases["trut"] == "run-unit-tests"
    assert c.generated_aliases["rut"] == "run-unit-tests"


def test_catalog_build_sorts_by_category_then_display_name() -> None:
    entries = [
        catalog.CanonicalEntry("run-unit-tests", "Run Unit Tests", ".", "Testing", "trut", (), "2026-10-10", "h1", "h2"),
        catalog.CanonicalEntry("agent-plan", "Agent Plan", ".", "Agent Workflow", "ap", (), "2026-10-10", "h3", "h4"),
    ]
    c = catalog.Catalog.build(entries, "2026-10-10")
    assert c.entries[0].name == "agent-plan"
    assert c.entries[1].name == "run-unit-tests"


def test_catalog_load_roundtrip(tmp_path: Path) -> None:
    entry = catalog.CanonicalEntry(
        "run-unit-tests", "Run Unit Tests", "Run tests.", "Testing",
        "trut", ("rut",), "2026-10-10", "h1", "h2",
    )
    c = catalog.Catalog.build([entry], "2026-10-10")
    path = tmp_path / "catalog.json"
    c.save(path)
    loaded = catalog.Catalog.load(path)
    assert loaded is not None
    assert len(loaded.entries) == 1
    assert loaded.entries[0].name == "run-unit-tests"
    assert loaded.entries[0].aliases == ("rut",)


def test_render_toc_sorted_by_category_then_display_name() -> None:
    entries = [
        catalog.CanonicalEntry("run-unit-tests", "Run Unit Tests", "Run tests.", "Testing", "trut", ("rut",), "2026-10-10", "h1", "h2"),
        catalog.CanonicalEntry("agent-plan", "Agent Plan", "Plan work.", "Agent Workflow", "ap", (), "2026-10-10", "h3", "h4"),
    ]
    c = catalog.Catalog.build(entries, "2026-10-10")
    toc = c.render_toc()
    agent_idx = toc.index("Agent Workflow")
    testing_idx = toc.index("## Testing")
    assert agent_idx < testing_idx
    assert "Run Unit Tests" in toc
    assert "(`trut`)" in toc
    assert "rut" in toc


def test_render_toc_one_bullet_per_canonical_skill() -> None:
    entries = [
        catalog.CanonicalEntry("run-unit-tests", "Run Unit Tests", "Run tests.", "Testing", "trut", ("rut",), "2026-10-10", "h1", "h2"),
    ]
    c = catalog.Catalog.build(entries, "2026-10-10")
    toc = c.render_toc()
    assert toc.count("- ") == 1


def test_generate_alias_skill_md_contains_marker() -> None:
    text = catalog.generate_alias_skill_md("trut", "run-unit-tests", "2026-10-10", "Run tests.")
    m = catalog.GENERATED_MARKER_RE.search(text)
    assert m is not None
    assert m.group("canonical") == "run-unit-tests"
    assert m.group("date") == "2026-10-10"
    fm = catalog.parse_frontmatter(text)
    assert fm["name"] == "trut"


def test_write_generated_aliases_creates_directories(tmp_path: Path) -> None:
    entry = catalog.CanonicalEntry(
        "run-unit-tests", "Run Unit Tests", "Run tests.", "Testing",
        "trut", ("rut",), "2026-10-10", "h1", "h2",
    )
    c = catalog.Catalog.build([entry], "2026-10-10")
    sc = catalog.SkillCatalog(tmp_path)
    sc._write_generated_aliases(c, "2026-10-10")
    assert (tmp_path / "trut" / "SKILL.md").is_file()
    assert (tmp_path / "rut" / "SKILL.md").is_file()
    assert "run-unit-tests" in (tmp_path / "trut" / "SKILL.md").read_text(encoding="utf-8")


def test_write_generated_aliases_refuses_human_owned_collision(tmp_path: Path) -> None:
    import pytest
    (tmp_path / "trut").mkdir()
    (tmp_path / "trut" / "SKILL.md").write_text(
        "---\nname: trut\ndescription: Hand-written.\n---\n\n# trut\n\nBody.\n",
        encoding="utf-8",
    )
    entry = catalog.CanonicalEntry(
        "run-unit-tests", "Run Unit Tests", "Run tests.", "Testing",
        "trut", (), "2026-10-10", "h1", "h2",
    )
    c = catalog.Catalog.build([entry], "2026-10-10")
    sc = catalog.SkillCatalog(tmp_path)
    with pytest.raises(catalog.HumanOwnedCollision):
        sc._write_generated_aliases(c, "2026-10-10")


def test_retire_obsolete_aliases_removes_generated_only(tmp_path: Path) -> None:
    (tmp_path / "old-alias").mkdir()
    (tmp_path / "old-alias" / "SKILL.md").write_text(
        "---\nname: old-alias\ndescription: Alias.\n---\n\n"
        "<!-- generated:some-skill:2026-10-10 -->\n",
        encoding="utf-8",
    )
    c = catalog.Catalog.build([], "2026-10-10")
    sc = catalog.SkillCatalog(tmp_path)
    sc._retire_obsolete_aliases(c)
    assert not (tmp_path / "old-alias").exists()


def test_retire_obsolete_aliases_preserves_human_owned(tmp_path: Path) -> None:
    (tmp_path / "human-alias").mkdir()
    (tmp_path / "human-alias" / "SKILL.md").write_text(
        "---\nname: human-alias\ndescription: Human.\n---\n\n# human-alias\n\nBody.\n",
        encoding="utf-8",
    )
    c = catalog.Catalog.build([], "2026-10-10")
    sc = catalog.SkillCatalog(tmp_path)
    sc._retire_obsolete_aliases(c)
    assert (tmp_path / "human-alias").exists()


def test_validate_rejects_duplicate_shorthands() -> None:
    import pytest
    # tsab is valid for both skill-a (initials: s,a) and skill-b (initials: s,b)
    entries = [
        catalog.CanonicalEntry("skill-a", "Skill A", "A.", "Testing", "tsab", (), "2026-10-10", "h1", "h2"),
        catalog.CanonicalEntry("skill-b", "Skill B", "B.", "Testing", "tsab", (), "2026-10-10", "h3", "h4"),
    ]
    c = catalog.Catalog.build(entries, "2026-10-10")
    with pytest.raises(catalog.DuplicateName):
        c.validate()


def test_validate_rejects_shorthand_without_category_prefix() -> None:
    import pytest
    entries = [
        catalog.CanonicalEntry(
            "run-unit-tests", "Run Unit Tests", "R.", "Testing", "rut", (), "2026-10-10", "h1", "h2"
        ),
    ]
    # "rut" starts with "r" (Reporting prefix) not "t" (Testing prefix)
    c = catalog.Catalog(1, "2026-10-10", tuple(entries), {"rut": "run-unit-tests"})
    with pytest.raises(catalog.InvalidShorthand):
        c.validate()


def test_validate_rejects_empty_entries() -> None:
    import pytest
    c = catalog.Catalog.build([], "2026-10-10")
    with pytest.raises(catalog.EmptyScan):
        c.validate()


def _make_skill_tree(tmp_path: Path) -> None:
    skill_dir = tmp_path / "run-unit-tests"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        _skill_text("run-unit-tests", "Testing", "trut", aliases="rut"),
        encoding="utf-8",
    )


def test_update_creates_catalog_and_toc(tmp_path: Path) -> None:
    import io
    _make_skill_tree(tmp_path)
    sc = catalog.SkillCatalog(tmp_path, cache_path=tmp_path / "cache.json")
    assert sc.update(out=io.StringIO()) == 0
    assert (tmp_path / catalog.CATALOG_FILENAME).is_file()
    assert (tmp_path / catalog.TOC_FILENAME).is_file()


def test_check_returns_nonzero_on_stale_toc(tmp_path: Path) -> None:
    import io
    _make_skill_tree(tmp_path)
    sc = catalog.SkillCatalog(tmp_path, cache_path=tmp_path / "cache.json")
    sc.update(out=io.StringIO())
    (tmp_path / catalog.TOC_FILENAME).write_text("stale\n", encoding="utf-8")
    assert sc.check(out=io.StringIO()) != 0


def test_show_warm_cache_reads_no_skill_bodies(tmp_path: Path) -> None:
    import io, unittest.mock
    _make_skill_tree(tmp_path)
    sc = catalog.SkillCatalog(tmp_path, cache_path=tmp_path / "cache.json")
    sc.update(out=io.StringIO())

    read_calls: list[str] = []
    original = Path.read_text

    def spy(self: Path, **kwargs):  # type: ignore[no-untyped-def]
        if self.name == "SKILL.md":
            read_calls.append(str(self))
        return original(self, **kwargs)

    with unittest.mock.patch.object(Path, "read_text", spy):
        sc.show(out=io.StringIO())

    assert read_calls == []
