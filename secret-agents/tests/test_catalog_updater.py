"""Behavioral tests for the manifest-backed skills catalog."""

from __future__ import annotations

import importlib.util
import io
import json
import re
import sys
import unittest.mock
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
CATALOG_SCRIPT = ROOT / "skills" / "skill-authoring" / "query-all-skills" / "scripts" / "catalog.py"


def _load_catalog() -> ModuleType:
    spec = importlib.util.spec_from_file_location("catalog", CATALOG_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["catalog"] = module
    spec.loader.exec_module(module)
    return module


catalog = _load_catalog()


def _collection(name: str) -> dict[str, str]:
    return {"name": name, "display_name": name.title(), "description": f"{name} collection."}


def _manifest(root: Path, collections: list[dict[str, str]], layout: str = "collections") -> None:
    (root / "collections.json").write_text(
        json.dumps({"schema_version": 1, "source_layout": layout, "collections": collections}), encoding="utf-8"
    )


def _skill(root: Path, collection: str, name: str, category: str = "Testing") -> Path:
    directory = root / collection / name
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Use {name}.\n---\n\n"
        f"# {name.replace('-', ' ').title()}\n\n"
        f"**Category:** {category} · **Updated:** 2026-10-15\n\n"
        "Canonical instruction body.\n",
        encoding="utf-8",
    )
    return directory


def _published_files(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and path.name in {"catalog.json", "TOC.md", "SKILL.md"}
    }


def test_parse_header_accepts_canonical_headers() -> None:
    new = "# Skill\n\n**Category:** Testing · **Updated:** 2026-10-15\n"

    assert catalog.parse_skill_header(new).category == "Testing"


def test_collection_scanner_reads_only_declared_collection_roots(tmp_path: Path) -> None:
    _manifest(tmp_path, [_collection("testing")])
    _skill(tmp_path, "testing", "test-skill")

    sources = catalog.SkillCatalog(tmp_path)._scan_canonical_sources()

    assert sources == (catalog.CanonicalSource("testing", tmp_path / "testing" / "test-skill", "testing/test-skill"),)


def test_collection_scanner_allows_readme_and_ignores_generated_projection(tmp_path: Path) -> None:
    _manifest(tmp_path, [_collection("testing")])
    _skill(tmp_path, "testing", "test-skill")
    (tmp_path / "testing" / "README.md").write_text("# Testing\n", encoding="utf-8")
    _skill(tmp_path / "_generated", "ignored", "not-a-canonical-source")

    assert [source.source_path for source in catalog.SkillCatalog(tmp_path)._scan_canonical_sources()] == [
        "testing/test-skill"
    ]


def test_undeclared_collection_aborts_before_publication(tmp_path: Path) -> None:
    _manifest(tmp_path, [_collection("testing")])
    _skill(tmp_path, "testing", "test-skill")
    _skill(tmp_path, "undeclared", "unowned-skill")
    before = _published_files(tmp_path)

    assert catalog.SkillCatalog(tmp_path, tmp_path / "cache.json").update(io.StringIO()) == 1

    assert before == _published_files(tmp_path)


def test_root_level_skill_file_aborts_before_publication(tmp_path: Path) -> None:
    _manifest(tmp_path, [_collection("testing")])
    _skill(tmp_path, "testing", "test-skill")
    misplaced = tmp_path / "SKILL.md"
    misplaced.write_text("misplaced", encoding="utf-8")
    before = _published_files(tmp_path)

    assert catalog.SkillCatalog(tmp_path, tmp_path / "cache.json").update(io.StringIO()) == 1

    assert before == _published_files(tmp_path)


def test_collection_scanner_rejects_missing_or_misplaced_skill_files_with_paths(tmp_path: Path) -> None:
    _manifest(tmp_path, [_collection("testing")])
    missing = tmp_path / "testing" / "missing-skill"
    missing.mkdir(parents=True)
    with pytest.raises(catalog.CatalogError, match=re.escape(str(missing))):
        catalog.SkillCatalog(tmp_path)._scan_canonical_sources()

    misplaced = tmp_path / "testing" / "SKILL.md"
    missing.rmdir()
    misplaced.write_text("bad", encoding="utf-8")
    with pytest.raises(catalog.CatalogError, match=re.escape(str(misplaced))):
        catalog.SkillCatalog(tmp_path)._scan_canonical_sources()


def test_duplicate_canonical_names_across_collections_abort_before_publication(tmp_path: Path) -> None:
    _manifest(tmp_path, [_collection("alpha"), _collection("beta")])
    _skill(tmp_path, "alpha", "first-skill")
    duplicate = _skill(tmp_path, "beta", "second-skill") / "SKILL.md"
    duplicate.write_text(
        duplicate.read_text(encoding="utf-8").replace("name: second-skill", "name: first-skill"), encoding="utf-8"
    )
    before = _published_files(tmp_path)

    assert catalog.SkillCatalog(tmp_path, tmp_path / "cache.json").update(io.StringIO()) == 1

    assert before == _published_files(tmp_path)


def test_post_move_baseline_matches_canonical_collection_instruction_bodies_and_projection() -> None:
    baseline = json.loads(
        (ROOT / "tests" / "fixtures" / "categorized-skills-library-baseline.json").read_text(encoding="utf-8")
    )
    skills_root = ROOT / "skills"
    manifest = json.loads((skills_root / "collections.json").read_text(encoding="utf-8"))
    assert manifest["source_layout"] == "collections"
    sources = catalog.SkillCatalog(skills_root)._scan_canonical_sources()
    actual = []
    for source in sources:
        assert len(Path(source.source_path).parts) == 2
        text = (source.directory / "SKILL.md").read_text(encoding="utf-8")
        actual.append(
            {
                "name": catalog.parse_frontmatter(text)["name"],
                "instruction_body_hash": catalog.compute_instruction_body_hash(text),
            }
        )

    actual_by_name = {skill["name"]: skill["instruction_body_hash"] for skill in actual}
    baseline_by_name = {skill["name"]: skill["instruction_body_hash"] for skill in baseline["skills"]}
    authoring_contract_rewrites = {
        # These five authoring contracts deliberately describe the new
        # collection/projection model rather than retired flat-source paths.
        "install-skills",
        "query-all-skills",
        "update-skill",
        "update-skills-readme",
        "write-skill",
    }
    canonical_source_path_repairs = {
        # These thirteen workflows retain their behavior; only their canonical
        # source paths changed when the library moved into collections.
        "agent-plan",
        "checkin-receipt-create",
        "checkin-receipt-range",
        "checkin-rollup",
        "jira-human-ticket-create",
        "ready-player-one",
        "report-cost-analysis",
        "report-receipt",
        "report-rollup",
        "report-status",
        "unreal-reset-build-env",
        "update-claude-pricing-doc",
        "update-model-routing",
    }
    invocation_cleanup = {"run-unit-tests"}
    retired_work_tracking_names = {"checkin-receipt-create", "checkin-receipt-range", "checkin-rollup"}
    published_work_tracking_names = {
        "daily-note-create",
        "perforce-receipt-create",
        "perforce-receipt-range",
        "perforce-rollup",
        "git-receipt-create",
        "git-receipt-range",
        "git-rollup",
    }
    intentionally_rewritten_contracts = authoring_contract_rewrites | canonical_source_path_repairs | invocation_cleanup

    assert set(actual_by_name) == (set(baseline_by_name) - retired_work_tracking_names) | published_work_tracking_names
    assert len(authoring_contract_rewrites) == 5
    assert len(canonical_source_path_repairs) == 13
    assert len(invocation_cleanup) == 1
    assert len(intentionally_rewritten_contracts) == 19
    assert {
        name
        for name, instruction_hash in baseline_by_name.items()
        if name in actual_by_name and actual_by_name[name] != instruction_hash
    } == intentionally_rewritten_contracts - retired_work_tracking_names
    catalog_data = json.loads((skills_root / "catalog.json").read_text(encoding="utf-8"))
    names = set(actual_by_name)
    assert "generated_projection" not in catalog_data
    assert {entry["name"] for entry in catalog_data["entries"]} == names
    assert all(entry["source_path"].count("/") == 1 for entry in catalog_data["entries"])


def test_work_tracking_publication_exposes_replacements_and_retires_checkin_projections() -> None:
    skills_root = ROOT / "skills"
    published_names = {
        entry["name"] for entry in json.loads((skills_root / "catalog.json").read_text(encoding="utf-8"))["entries"]
    }
    expected = {
        "daily-note-create",
        "perforce-receipt-create",
        "perforce-receipt-range",
        "perforce-rollup",
        "git-receipt-create",
        "git-receipt-range",
        "git-rollup",
        "report-receipt",
        "report-status",
        "report-rollup",
    }

    assert expected <= published_names
    assert not {"checkin-receipt-create", "checkin-receipt-range", "checkin-rollup"} & published_names
    entries = json.loads((skills_root / "catalog.json").read_text(encoding="utf-8"))["entries"]
    source_paths = {entry["name"]: entry["source_path"] for entry in entries}
    assert all((skills_root / source_paths[name] / "SKILL.md").is_file() for name in expected)


def test_update_records_canonical_source_paths_without_generating_adapters(tmp_path: Path) -> None:
    _manifest(tmp_path, [_collection("testing")])
    _skill(tmp_path, "testing", "test-skill")

    assert catalog.SkillCatalog(tmp_path, tmp_path / "cache.json").update(io.StringIO()) == 0

    canonical = tmp_path / "testing" / "test-skill" / "SKILL.md"
    catalog_data = json.loads((tmp_path / "catalog.json").read_text(encoding="utf-8"))
    assert catalog.parse_frontmatter(canonical.read_text(encoding="utf-8"))["name"] == "test-skill"
    assert catalog_data["entries"][0]["source_path"] == "testing/test-skill"
    assert "generated_projection" not in catalog_data
    assert not (tmp_path / "_generated").exists()


def test_update_publishes_source_paths_without_generated_adapters(tmp_path: Path) -> None:
    _manifest(tmp_path, [_collection("testing")])
    canonical = _skill(tmp_path, "testing", "test-skill") / "SKILL.md"

    assert catalog.SkillCatalog(tmp_path, tmp_path / "cache.json").update(io.StringIO()) == 0

    catalog_data = json.loads((tmp_path / "catalog.json").read_text(encoding="utf-8"))
    assert catalog_data["entries"][0]["source_path"] == "testing/test-skill"
    assert "generated_projection" not in catalog_data
    assert not (tmp_path / "_generated").exists()
    assert canonical.is_file()


def test_collection_then_category_toc_is_deterministic(tmp_path: Path) -> None:
    _manifest(tmp_path, [_collection("zeta"), _collection("alpha")])
    _skill(tmp_path, "zeta", "first-skill")
    _skill(tmp_path, "alpha", "second-skill")
    instance = catalog.SkillCatalog(tmp_path, tmp_path / "cache.json")

    assert instance.update(io.StringIO()) == 0
    first_toc = (tmp_path / "TOC.md").read_text(encoding="utf-8")
    assert instance.update(io.StringIO()) == 0

    assert (tmp_path / "TOC.md").read_text(encoding="utf-8") == first_toc
    assert first_toc.index("## Zeta") < first_toc.index("## Alpha")


@pytest.mark.parametrize("colliding_name", ["test-skill", "second-skill"])
def test_human_owned_projection_collision_aborts_without_mutation(tmp_path: Path, colliding_name: str) -> None:
    _manifest(tmp_path, [_collection("testing")])
    _skill(tmp_path, "testing", "test-skill")
    _skill(tmp_path, "testing", "second-skill")
    collision = tmp_path / "_generated" / colliding_name
    collision.mkdir(parents=True)
    (collision / "SKILL.md").write_text("human-owned", encoding="utf-8")
    (tmp_path / "catalog.json").write_text("old catalog", encoding="utf-8")
    (tmp_path / "TOC.md").write_text("old toc", encoding="utf-8")
    before = _published_files(tmp_path)

    assert catalog.SkillCatalog(tmp_path, tmp_path / "cache.json").update(io.StringIO()) == 1

    assert before == _published_files(tmp_path)


def test_warm_show_reads_no_canonical_skill_bodies(tmp_path: Path) -> None:
    _manifest(tmp_path, [_collection("testing")])
    _skill(tmp_path, "testing", "test-skill")
    instance = catalog.SkillCatalog(tmp_path, tmp_path / "cache.json")
    assert instance.update(io.StringIO()) == 0
    reads: list[str] = []
    original = Path.read_text

    def spy(path: Path, **kwargs: Any) -> str:
        if path.name == "SKILL.md" and "_generated" not in path.parts:
            reads.append(str(path))
        return original(path, **kwargs)

    with unittest.mock.patch.object(Path, "read_text", spy):
        assert instance.show(io.StringIO()) == 0

    assert reads == []


def test_warm_show_refreshes_after_collection_membership_changes(tmp_path: Path) -> None:
    _manifest(tmp_path, [_collection("testing")])
    _skill(tmp_path, "testing", "test-skill")
    instance = catalog.SkillCatalog(tmp_path, tmp_path / "cache.json")
    assert instance.update(io.StringIO()) == 0
    _skill(tmp_path, "testing", "second-skill")
    output = io.StringIO()

    assert instance.show(output) == 0

    assert "/second-skill" in output.getvalue()


def test_warm_show_rejects_human_owned_obsolete_generated_directory(tmp_path: Path) -> None:
    _manifest(tmp_path, [_collection("testing")])
    _skill(tmp_path, "testing", "test-skill")
    instance = catalog.SkillCatalog(tmp_path, tmp_path / "cache.json")
    assert instance.update(io.StringIO()) == 0
    human_owned = tmp_path / "_generated" / "human-skill"
    human_owned.mkdir(parents=True)
    (human_owned / "SKILL.md").write_text("human-owned", encoding="utf-8")

    assert instance.show(io.StringIO()) == 1


def test_check_detects_obsolete_generated_adapters_without_mutation(tmp_path: Path) -> None:
    _manifest(tmp_path, [_collection("testing")])
    _skill(tmp_path, "testing", "test-skill")
    instance = catalog.SkillCatalog(tmp_path, tmp_path / "cache.json")
    assert instance.update(io.StringIO()) == 0
    adapter = tmp_path / "_generated" / "test-skill" / "SKILL.md"
    adapter.parent.mkdir(parents=True)
    adapter.write_text("<!-- generated-projection:test-skill:2026-10-15 -->\n", encoding="utf-8")
    before = _published_files(tmp_path)

    assert instance.check(io.StringIO()) == 1

    assert before == _published_files(tmp_path)


def test_check_rejects_human_owned_obsolete_generated_directory(tmp_path: Path) -> None:
    _manifest(tmp_path, [_collection("testing")])
    _skill(tmp_path, "testing", "test-skill")
    instance = catalog.SkillCatalog(tmp_path, tmp_path / "cache.json")
    assert instance.update(io.StringIO()) == 0
    human_owned = tmp_path / "_generated" / "human-skill"
    human_owned.mkdir(parents=True)
    (human_owned / "SKILL.md").write_text("human-owned", encoding="utf-8")

    assert instance.check(io.StringIO()) == 1


def test_publication_rolls_back_projection_when_catalog_write_fails(tmp_path: Path) -> None:
    _manifest(tmp_path, [_collection("testing")])
    _skill(tmp_path, "testing", "test-skill")
    instance = catalog.SkillCatalog(tmp_path, tmp_path / "cache.json")
    assert instance.update(io.StringIO()) == 0
    _skill(tmp_path, "testing", "second-skill")
    before = _published_files(tmp_path)
    original = catalog._atomic_write

    def fail_catalog_write(path: Path, text: str) -> None:
        if path == tmp_path / "catalog.json":
            raise OSError("simulated disk failure")
        original(path, text)

    with unittest.mock.patch.object(catalog, "_atomic_write", fail_catalog_write):
        assert instance.update(io.StringIO()) == 1

    assert before == _published_files(tmp_path)


def test_failed_initial_publication_leaves_no_generated_artifacts(tmp_path: Path) -> None:
    _manifest(tmp_path, [_collection("testing")])
    _skill(tmp_path, "testing", "test-skill")
    instance = catalog.SkillCatalog(tmp_path, tmp_path / "cache.json")
    before = _published_files(tmp_path)
    original = catalog._atomic_write

    def fail_catalog_write(path: Path, text: str) -> None:
        if path == tmp_path / "catalog.json":
            raise OSError("simulated disk failure")
        original(path, text)

    with unittest.mock.patch.object(catalog, "_atomic_write", fail_catalog_write):
        assert instance.update(io.StringIO()) == 1

    assert before == _published_files(tmp_path)


def test_publication_rolls_back_indexes_when_toc_write_fails(tmp_path: Path) -> None:
    _manifest(tmp_path, [_collection("testing")])
    _skill(tmp_path, "testing", "test-skill")
    instance = catalog.SkillCatalog(tmp_path, tmp_path / "cache.json")
    assert instance.update(io.StringIO()) == 0
    _skill(tmp_path, "testing", "second-skill")
    before = _published_files(tmp_path)
    original = catalog._atomic_write

    def fail_toc_write(path: Path, text: str) -> None:
        if path == tmp_path / "TOC.md":
            raise OSError("simulated disk failure")
        original(path, text)

    with unittest.mock.patch.object(catalog, "_atomic_write", fail_toc_write):
        assert instance.update(io.StringIO()) == 1

    assert before == _published_files(tmp_path)


def test_obsolete_adapter_cleanup_failure_does_not_rollback_committed_catalog(tmp_path: Path) -> None:
    _manifest(tmp_path, [_collection("testing")])
    _skill(tmp_path, "testing", "test-skill")
    instance = catalog.SkillCatalog(tmp_path, tmp_path / "cache.json")
    assert instance.update(io.StringIO()) == 0
    _skill(tmp_path, "testing", "second-skill")
    generated_root = tmp_path / "_generated"
    adapter = generated_root / "test-skill" / "SKILL.md"
    adapter.parent.mkdir(parents=True)
    adapter.write_text("<!-- generated-projection:test-skill:2026-10-15 -->\n", encoding="utf-8")
    original_rmtree = catalog.shutil.rmtree

    def fail_after_partial_backup_cleanup(path: Path, *args: object, **kwargs: object) -> None:
        if path == generated_root:
            raise OSError("simulated backup cleanup failure")
        original_rmtree(path, *args, **kwargs)

    with unittest.mock.patch.object(catalog.shutil, "rmtree", fail_after_partial_backup_cleanup):
        assert instance.update(io.StringIO()) == 1

    catalog_data = json.loads((tmp_path / "catalog.json").read_text(encoding="utf-8"))
    assert {entry["name"] for entry in catalog_data["entries"]} == {"test-skill", "second-skill"}
    assert adapter.is_file()


def test_flat_manifest_mode_is_rejected_after_source_move(tmp_path: Path) -> None:
    _manifest(tmp_path, [], layout="flat")

    with pytest.raises(catalog.InvalidManifest, match="source_layout"):
        catalog.SkillCatalog(tmp_path, tmp_path / "cache.json")._scan_canonical_sources()


def test_update_retires_only_marker_owned_root_legacy_adapters(tmp_path: Path) -> None:
    _manifest(tmp_path, [_collection("testing")])
    _skill(tmp_path, "testing", "test-skill")
    legacy = tmp_path / "old-test-skill"
    legacy.mkdir()
    (legacy / "SKILL.md").write_text("<!-- generated:test-skill:2026-10-15 -->\n# old-test-skill\n", encoding="utf-8")

    assert catalog.SkillCatalog(tmp_path, tmp_path / "cache.json").update(io.StringIO()) == 0

    assert not legacy.exists()
    assert not (tmp_path / "_generated").exists()


def test_update_records_a_canonical_rename_without_generating_an_adapter(tmp_path: Path) -> None:
    _manifest(tmp_path, [_collection("testing")])
    original = _skill(tmp_path, "testing", "old-skill")
    instance = catalog.SkillCatalog(tmp_path, tmp_path / "cache.json")
    assert instance.update(io.StringIO()) == 0
    original.rename(tmp_path / "testing" / "new-skill")
    renamed_skill = tmp_path / "testing" / "new-skill" / "SKILL.md"
    renamed_skill.write_text(
        renamed_skill.read_text(encoding="utf-8").replace("name: old-skill", "name: new-skill"), encoding="utf-8"
    )

    assert instance.update(io.StringIO()) == 0

    catalog_data = json.loads((tmp_path / "catalog.json").read_text(encoding="utf-8"))
    assert [entry["name"] for entry in catalog_data["entries"]] == ["new-skill"]
    assert not (tmp_path / "_generated").exists()


def test_default_skills_root_uses_vault_override(tmp_path: Path) -> None:
    vault_root = tmp_path / "vault"

    assert catalog._default_skills_root(vault_root) == vault_root / "handbag-of-holding/secret-agents/skills"
