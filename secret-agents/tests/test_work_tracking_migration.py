"""Read-only migration inventory and preflight contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from secret_agents_work_tracking.cli import main
from secret_agents_work_tracking.errors import MigrationPreflightError
from secret_agents_work_tracking.migration import build_inventory, preflight_migration, write_audit
from secret_agents_work_tracking.models import MigrationEntry, Workspace
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


def github_receipt() -> str:
    return (
        receipt("https://github.com/acme/repo/pull/1", "Git body.", kind="source-control-receipt")
        .replace("source_system: manual", "source_system: github")
        .replace("sources: []", "sources: []\ngithub_activity: merged_pull_request\npr_commit_urls: []")
    )


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
