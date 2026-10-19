"""Read-only migration inventory and preflight contracts."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from pathlib import Path

import pytest

import secret_agents_work_tracking.migration as migration
from secret_agents_work_tracking.cli import main
from secret_agents_work_tracking.errors import MigrationPreflightError
from secret_agents_work_tracking.evidence import parse_evidence
from secret_agents_work_tracking.migration import apply_migration, build_inventory, preflight_migration, write_audit
from secret_agents_work_tracking.models import EvidenceRecord, MigrationAudit, MigrationEntry, Workspace
from secret_agents_work_tracking.workspace import resolve_workspace

CONFIGURATION = """\
schema: work-tracking/v1
tracking_root: Work Tracking
timezone: America/Los_Angeles
locations:
  receipts: Receipts
  daily_notes: Daily
  perforce_checkins: Checkins/perforce
  git_checkins: Checkins/git
  status_reports: Reports/Status
  monthly_reports: Reports/Monthly
  annual_reviews: Reports/Annual
  templates: Templates
  imports: Imports
  ledgers: Ledgers
"""


def test_inventory_classifies_known_content_without_creating_destinations(tmp_path: Path) -> None:
    vault = create_legacy_vault(tmp_path)

    inventory = build_inventory(workspace_for(vault))

    by_source = {entry.source.relative_to(vault).as_posix(): entry for entry in inventory.classified}
    receipt = by_source["Receipts/2026/receipt.md"]
    assert receipt.destination == vault / "Work Tracking/Receipts/2026/receipt.md"
    assert receipt.classification == "receipt"
    assert receipt.content_hash == hashlib.sha256(receipt.source.read_bytes()).hexdigest()
    assert receipt.rationale == "legacy Receipts root"
    assert {entry.classification for entry in inventory.classified} == {
        "receipt",
        "daily-note",
        "perforce-checkin",
        "git-checkin",
        "status-report",
        "annual-review",
        "template",
        "import",
        "ledger",
    }
    assert [path.relative_to(vault).as_posix() for path in inventory.untouched] == ["Projects/idea.md"]
    assert not (vault / "Work Tracking").exists()


def test_preflight_refuses_an_existing_destination_without_writing(tmp_path: Path) -> None:
    vault = create_legacy_vault(tmp_path)
    destination = vault / "Work Tracking/Receipts/2026/receipt.md"
    destination.parent.mkdir(parents=True)
    destination.write_text("existing", encoding="utf-8")

    with pytest.raises(MigrationPreflightError, match="destination already exists"):
        preflight_migration(build_inventory(workspace_for(vault)))

    assert destination.read_text(encoding="utf-8") == "existing"
    assert (vault / "Receipts/2026/receipt.md").is_file()


def test_preflight_refuses_conflicting_stable_source_ids(tmp_path: Path) -> None:
    vault = create_legacy_vault(tmp_path)
    duplicate = vault / "Receipts/2026/duplicate.md"
    duplicate.write_text(receipt("manual:receipt", "Different receipt body."), encoding="utf-8")

    with pytest.raises(MigrationPreflightError, match="conflicting source_id"):
        preflight_migration(build_inventory(workspace_for(vault)))

    assert duplicate.is_file()
    assert not (vault / "Work Tracking").exists()


def test_preflight_refuses_an_unresolved_markdown_or_wikilink(tmp_path: Path) -> None:
    vault = create_legacy_vault(tmp_path)
    receipt_path = vault / "Receipts/2026/receipt.md"
    receipt_path.write_text(
        receipt("manual:receipt", "See [[Missing evidence]] and [missing](missing.md)."), encoding="utf-8"
    )

    with pytest.raises(MigrationPreflightError, match="unresolved link"):
        preflight_migration(build_inventory(workspace_for(vault)))

    assert receipt_path.is_file()
    assert not (vault / "Work Tracking").exists()


def test_preflight_ignores_iso_date_wikilink_template_placeholders(tmp_path: Path) -> None:
    vault = create_legacy_vault(tmp_path)
    template = vault / "Templates/receipt.md"
    template.write_text("# Template\n\n- [[YYYY-MM-DD]]\n", encoding="utf-8")

    apply_migration(preflight_migration(build_inventory(workspace_for(vault))))

    assert "[[YYYY-MM-DD]]" in (vault / "Work Tracking/Templates/receipt.md").read_text(encoding="utf-8")


def test_preflight_preserves_repository_relative_markdown_links(tmp_path: Path) -> None:
    vault = create_legacy_vault(tmp_path)
    receipt_path = vault / "Receipts/2026/receipt.md"
    receipt_path.write_text(
        receipt(
            "manual:receipt",
            "See [build script](laika-package-unreal/builder/src/build.sh), [repo](laika-package-unreal), and "
            "[source](/Users/Shared/project/main.cpp:29).",
        ),
        encoding="utf-8",
    )

    preflight_migration(build_inventory(workspace_for(vault)))


def test_apply_ignores_wikilinks_inside_inline_code(tmp_path: Path) -> None:
    vault = create_legacy_vault(tmp_path)
    receipt_path = vault / "Receipts/2026/receipt.md"
    daily_path = vault / "Daily/2026/day.md"
    receipt_path.write_text(receipt("manual:receipt", "Document `[[name]]`, then see [[day]]."), encoding="utf-8")
    daily_path.write_text(receipt("manual:daily", "Daily body.", kind="daily-note"), encoding="utf-8")

    apply_migration(preflight_migration(build_inventory(workspace_for(vault))))

    migrated = vault / "Work Tracking/Receipts/2026/receipt.md"
    text = migrated.read_text(encoding="utf-8")
    assert "`[[name]]`" in text
    assert "[[Work Tracking/Daily/2026/day.md]]" in text


def test_apply_normalizes_a_legacy_perforce_receipt_without_changing_its_body(tmp_path: Path) -> None:
    vault = create_legacy_vault(tmp_path)
    source = vault / "Checkins/perforce/2025/2025-09/CK-6134-vistest-config-paths.md"
    original_body = "# Checkin Receipt — CL 6134 (2025-09-18)\n\nUpdated the configuration path.\n"
    write(source, legacy_perforce_receipt(original_body))

    apply_migration(preflight_migration(build_inventory(workspace_for(vault))))

    migrated = vault / "Work Tracking/Checkins/perforce/2025/2025-09/CK-6134-vistest-config-paths.md"
    record = parse_evidence(migrated)
    assert isinstance(record, EvidenceRecord)
    assert record.kind == "source-control-receipt"
    assert record.source_system == "perforce"
    assert record.source_id == "6134"
    assert record.initiatives == ("VisTest/Config",)
    assert record.body == original_body


def test_apply_normalizes_a_legacy_perforce_receipt_without_a_source_marker(tmp_path: Path) -> None:
    vault = create_legacy_vault(tmp_path)
    source = vault / "Checkins/perforce/2026/2026-07/CK-7048-openexr-thirdparty-deps.md"
    write(source, legacy_perforce_receipt("Receipt body.\n").replace("source: perforce\n", ""))

    apply_migration(preflight_migration(build_inventory(workspace_for(vault))))

    migrated = vault / "Work Tracking/Checkins/perforce/2026/2026-07/CK-7048-openexr-thirdparty-deps.md"
    record = parse_evidence(migrated)
    assert isinstance(record, EvidenceRecord)
    assert record.source_system == "perforce"
    assert record.source_id == "6134"


def test_preflight_classifies_a_legacy_perforce_rollup_without_treating_it_as_evidence(tmp_path: Path) -> None:
    vault = create_legacy_vault(tmp_path)
    source = vault / "Checkins/perforce/2025/2025-09/rollups/ck-monthly-2025-09.md"
    write(source, legacy_perforce_rollup())

    plan = preflight_migration(build_inventory(workspace_for(vault)))

    entry = next(candidate for candidate in plan.inventory.classified if candidate.source == source)
    assert entry.classification == "perforce-rollup"
    assert entry.destination == vault / "Work Tracking/Checkins/perforce/2025/2025-09/rollups/ck-monthly-2025-09.md"


def test_inventory_leaves_a_top_level_perforce_handoff_untouched(tmp_path: Path) -> None:
    vault = create_legacy_vault(tmp_path)
    handoff = vault / "Checkins/perforce/BACKFILL_HANDBOFFS.md"
    write(handoff, "# Backfill handoffs\n")

    inventory = build_inventory(workspace_for(vault))

    assert handoff in inventory.untouched
    assert all(entry.source != handoff for entry in inventory.classified)


def test_apply_normalizes_a_frontmatter_free_daily_note_using_its_filename_date(tmp_path: Path) -> None:
    vault = create_legacy_vault(tmp_path)
    source = vault / "Daily/2026/2026-04/Daily-Note-2026-04-25_Builder-doc-n-sync.md"
    original_body = "# 2026-05-28 Thursday\n\n## Today's Work\n- Builder documentation\n"
    write(source, original_body)
    expected_source_id = f"manual:migration:{hashlib.sha256(source.read_bytes()).hexdigest()}"

    apply_migration(preflight_migration(build_inventory(workspace_for(vault))))

    migrated = vault / "Work Tracking/Daily/2026/2026-04/Daily-Note-2026-04-25_Builder-doc-n-sync.md"
    record = parse_evidence(migrated)
    assert isinstance(record, EvidenceRecord)
    assert record.kind == "daily-note"
    assert record.occurred_start == date(2026, 4, 25)
    assert record.occurred_end == date(2026, 4, 25)
    assert record.source_id == expected_source_id
    assert record.body == original_body


def test_apply_normalizes_a_daily_note_when_filename_and_heading_outvote_directory_month(tmp_path: Path) -> None:
    vault = create_legacy_vault(tmp_path)
    source = vault / "Daily/2026/2026-04/Daily-Note_2026-05-28_Builder-doc-n-sync.md"
    write(source, "# 2026-05-28 Thursday\n\n## Today's Work\n- Builder documentation\n")

    apply_migration(preflight_migration(build_inventory(workspace_for(vault))))

    migrated = vault / "Work Tracking/Daily/2026/2026-04/Daily-Note_2026-05-28_Builder-doc-n-sync.md"
    record = parse_evidence(migrated)
    assert isinstance(record, EvidenceRecord)
    assert record.occurred_start == date(2026, 5, 28)
    assert record.occurred_end == date(2026, 5, 28)


def test_inventory_leaves_a_frontmatter_free_daily_note_without_a_calendar_date_untouched(tmp_path: Path) -> None:
    vault = create_legacy_vault(tmp_path)
    source = vault / "Daily/2026/2026-05/break me up.md"
    write(source, "# Notes\n\nNo calendar date is available.\n")

    inventory = build_inventory(workspace_for(vault))

    assert source in inventory.untouched
    assert all(entry.source != source for entry in inventory.classified)


def test_apply_normalizes_a_frontmatter_free_receipt_using_its_filename_date_range(tmp_path: Path) -> None:
    vault = create_legacy_vault(tmp_path)
    source = vault / "Receipts/2026/2026-04/WR-2026-04-22_to_2026-04-23-test-uba.md"
    original_body = "## Work Receipt\n\n### Goal\n- Test UBA.\n"
    write(source, original_body)
    expected_source_id = f"manual:migration:{hashlib.sha256(source.read_bytes()).hexdigest()}"

    apply_migration(preflight_migration(build_inventory(workspace_for(vault))))

    migrated = vault / "Work Tracking/Receipts/2026/2026-04/WR-2026-04-22_to_2026-04-23-test-uba.md"
    record = parse_evidence(migrated)
    assert isinstance(record, EvidenceRecord)
    assert record.kind == "work-receipt"
    assert record.occurred_start == date(2026, 4, 22)
    assert record.occurred_end == date(2026, 4, 23)
    assert record.source_id == expected_source_id
    assert record.body == original_body


def test_inventory_leaves_a_frontmatter_free_receipt_without_dates_untouched(tmp_path: Path) -> None:
    vault = create_legacy_vault(tmp_path)
    source = vault / "Receipts/2026/Untitled.md"
    write(source, "## Work Receipt\n\nNo calendar date is available.\n")

    inventory = build_inventory(workspace_for(vault))

    assert source in inventory.untouched
    assert all(entry.source != source for entry in inventory.classified)


def test_inventory_indexes_markdown_stems_once_for_repeated_wikilinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = create_legacy_vault(tmp_path)
    receipt_path = vault / "Receipts/2026/receipt.md"
    receipt_path.write_text(receipt("manual:receipt", "See [[day]] and [[day]]."), encoding="utf-8")
    original_rglob = Path.rglob
    stem_index_scans = 0

    def count_stem_index_scans(path: Path, pattern: str) -> object:
        nonlocal stem_index_scans
        if path == vault and pattern == "*.md":
            stem_index_scans += 1
        return original_rglob(path, pattern)

    monkeypatch.setattr(Path, "rglob", count_stem_index_scans)

    build_inventory(workspace_for(vault))

    assert stem_index_scans == 1


def test_dry_run_audit_records_classified_and_untouched_paths(tmp_path: Path) -> None:
    vault = create_legacy_vault(tmp_path)
    plan = preflight_migration(build_inventory(workspace_for(vault)))

    audit_path = write_audit(plan, tmp_path / "audit.json")

    data = json.loads(audit_path.read_text(encoding="utf-8"))
    assert data["classified"][0]["content_hash_algorithm"] == "sha256"
    assert data["untouched"] == [str(vault / "Projects/idea.md")]
    assert not (vault / "Work Tracking").exists()


def test_semantic_hash_ignores_injected_frontmatter_and_equivalent_links(tmp_path: Path) -> None:
    vault = create_legacy_vault(tmp_path)
    receipt_path = vault / "Receipts/2026/receipt.md"
    receipt_path.write_text(receipt("manual:receipt", "See [daily](../../Daily/2026/day.md)."), encoding="utf-8")
    first_hash = inventory_entry(vault, receipt_path).semantic_hash
    receipt_path.write_text(
        receipt("manual:receipt", "See [[day]].").replace("status: draft", "status: draft\nmigration: generated"),
        encoding="utf-8",
    )

    assert inventory_entry(vault, receipt_path).semantic_hash == first_hash


def test_migration_inventory_cli_writes_a_dry_run_audit_without_tracking_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = create_legacy_vault(tmp_path)

    exit_code = main(["migration", "inventory", "--dry-run", "--vault", str(vault)])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["mode"] == "dry-run"
    assert output["untouched"] == [str(vault / "Projects/idea.md")]
    assert not (vault / "Work Tracking").exists()


def test_apply_moves_classified_files_rewrites_links_and_preserves_hashes(tmp_path: Path) -> None:
    vault = create_legacy_vault(tmp_path)
    receipt_path = vault / "Receipts/2026/receipt.md"
    daily_path = vault / "Daily/2026/day.md"
    receipt_path.write_text(receipt("manual:receipt", "See [daily](../../Daily/2026/day.md)."), encoding="utf-8")
    daily_path.write_text(receipt("manual:daily", "See [[receipt]].", kind="daily-note"), encoding="utf-8")

    audit = apply_migration(preflight_migration(build_inventory(workspace_for(vault))))

    moved_receipt = vault / "Work Tracking/Receipts/2026/receipt.md"
    moved_daily = vault / "Work Tracking/Daily/2026/day.md"
    assert isinstance(audit, MigrationAudit)
    assert not receipt_path.exists()
    assert not daily_path.exists()
    assert moved_receipt.is_file()
    assert moved_daily.is_file()
    assert "[daily](../../Daily/2026/day.md)" in moved_receipt.read_text(encoding="utf-8")
    assert "Work Tracking/Receipts/2026/receipt.md" in moved_daily.read_text(encoding="utf-8")
    assert audit.unresolved == ()
    assert all(item.output_hash for item in audit.moved)
    assert (vault / "Projects/idea.md").is_file()


def test_apply_preserves_markdown_fragments_and_wikilink_display_labels(tmp_path: Path) -> None:
    vault = create_legacy_vault(tmp_path)
    receipt_path = vault / "Receipts/2026/receipt.md"
    daily_path = vault / "Daily/2026/day.md"
    receipt_path.write_text(
        receipt(
            "manual:receipt",
            "See [daily](../../Daily/2026/day.md#Heading) and [[day#Heading|daily view]].",
        ),
        encoding="utf-8",
    )
    daily_path.write_text(receipt("manual:daily", "Daily body.", kind="daily-note"), encoding="utf-8")

    apply_migration(preflight_migration(build_inventory(workspace_for(vault))))

    migrated = (vault / "Work Tracking/Receipts/2026/receipt.md").read_text(encoding="utf-8")
    assert "[daily](../../Daily/2026/day.md#Heading)" in migrated
    assert "[[Work Tracking/Daily/2026/day.md#Heading|daily view]]" in migrated


def test_apply_rolls_back_every_completed_move_when_a_move_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = create_legacy_vault(tmp_path)
    plan = preflight_migration(build_inventory(workspace_for(vault)))
    original_rename = os.rename

    def fail_daily_move(source: Path, destination: Path) -> None:
        if source.name == "day.md" and source.parent.name == "2026":
            raise OSError("injected move failure")
        original_rename(source, destination)

    monkeypatch.setattr(os, "rename", fail_daily_move)

    audit = apply_migration(plan)

    assert audit.unresolved
    assert (vault / "Receipts/2026/receipt.md").is_file()
    assert (vault / "Daily/2026/day.md").is_file()
    assert not (vault / "Work Tracking/Receipts/2026/receipt.md").exists()
    assert (vault / "Projects/idea.md").is_file()


def test_apply_rolls_back_every_completed_move_when_link_staging_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = create_legacy_vault(tmp_path)
    receipt_path = vault / "Receipts/2026/receipt.md"
    receipt_path.write_text(receipt("manual:receipt", "See [[day]]."), encoding="utf-8")
    plan = preflight_migration(build_inventory(workspace_for(vault)))
    original_stage = migration._write_staged_document
    staged = 0

    def fail_second_stage(destination: Path, content: str) -> Path:
        nonlocal staged
        staged += 1
        if staged == 2:
            raise OSError("injected link staging failure")
        return original_stage(destination, content)

    monkeypatch.setattr(migration, "_write_staged_document", fail_second_stage)

    audit = apply_migration(plan)

    assert audit.unresolved
    assert (vault / "Receipts/2026/receipt.md").is_file()
    assert (vault / "Daily/2026/day.md").is_file()
    assert not (vault / "Work Tracking/Receipts/2026/receipt.md").exists()
    assert (vault / "Projects/idea.md").is_file()


def test_migration_apply_cli_emits_an_audit_for_a_successful_temporary_vault(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = create_legacy_vault(tmp_path)

    exit_code = main(["migration", "apply", "--vault", str(vault)])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["unresolved"] == []
    assert (vault / "Work Tracking/Receipts/2026/receipt.md").is_file()


def test_migration_inventory_cli_reports_a_preflight_blocker_without_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = create_legacy_vault(tmp_path)
    write(vault / "Receipts/2026/duplicate.md", receipt("manual:receipt", "Different receipt body."))

    exit_code = main(["migration", "inventory", "--dry-run", "--vault", str(vault)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "conflicting source_id" in captured.err
    assert "Traceback" not in captured.err


def workspace_for(vault: Path) -> Workspace:
    return resolve_workspace(None, vault, {}, vault / "agent-root")


def inventory_entry(vault: Path, source: Path) -> MigrationEntry:
    return next(entry for entry in build_inventory(workspace_for(vault)).classified if entry.source == source)


def create_legacy_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "work-tracking.yaml").write_text(CONFIGURATION, encoding="utf-8")
    write(vault / "Receipts/2026/receipt.md", receipt("manual:receipt", "Receipt body."))
    write(vault / "Daily/2026/day.md", receipt("manual:daily", "Daily body.", kind="daily-note"))
    write(vault / "Checkins/perforce/2026/change.md", perforce_receipt())
    write(vault / "Checkins/git/acme/repo/2026/pr.md", github_receipt())
    write(vault / "Status Reports/2026/status.md", "# Status\n")
    write(vault / "Reviews/Performance/2026/review.md", "# Annual review\n")
    write(vault / "Templates/receipt.md", "# Template\n")
    write(vault / "Raw Imports/book.txt", "Imported source\n")
    write(vault / "Cost Ledger.md", "# Cost ledger\n")
    write(vault / "Projects/idea.md", "# Unclassified\n")
    return vault


def receipt(source_id: str, body: str, *, kind: str = "work-receipt") -> str:
    return f"""---
kind: {kind}
occurred_start: 2026-10-17
occurred_end: 2026-10-17
source_system: manual
source_id: {source_id}
initiatives: [Work Tracking]
tags: [migration]
status: draft
sources: []
---
{body}
"""


def perforce_receipt() -> str:
    return (
        receipt('"123"', "Perforce body.", kind="source-control-receipt")
        .replace("source_system: manual", "source_system: perforce")
        .replace("sources: []", "sources: []\nchangelist: 123")
    )


def legacy_perforce_receipt(body: str) -> str:
    return f"""---
cl: 6134
date: 2025-09-18
author: mmccusker
client: vistest_mmccusker_dp58-130
stream: //vistest-vp/main
files: 1
lines_added: 6
lines_removed: 1
tags: [A]
arc: VisTest/Config
noise: false
status: draft
source: perforce
---
{body}"""


def legacy_perforce_rollup() -> str:
    return """---
status: draft
window: 2025-09
sources:
  - "[[change]]"
generated: 2026-10-13T08:10-07:00
---
# Checkin Rollup — ck-monthly-2025-09
"""


def github_receipt() -> str:
    return (
        receipt("https://github.com/acme/repo/pull/1", "Git body.", kind="source-control-receipt")
        .replace("source_system: manual", "source_system: github")
        .replace("sources: []", "sources: []\ngithub_activity: merged_pull_request\npr_commit_urls: []")
    )


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
