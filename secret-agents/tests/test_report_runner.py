"""Report automation must use the configured Work Tracking workspace."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_report.py"


def test_check_requires_work_tracking_configuration_without_creating_a_vault(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "status", "--check", "--vault", str(missing)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "work-tracking.yaml" in result.stderr
    assert not missing.exists()


@pytest.mark.parametrize("report", ["status", "monthly"])
def test_check_resolves_configured_named_locations_without_filesystem_side_effects(report: str, tmp_path: Path) -> None:
    _write_workspace_configuration(tmp_path)
    before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    result = subprocess.run(
        [sys.executable, str(SCRIPT), report, "--check", "--vault", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["vault"] == str(tmp_path)
    assert data["skill"] == {"status": "/report-status", "monthly": "/report-rollup"}[report]
    assert data["output_location"] == str(
        tmp_path / "Work Tracking" / "Reports" / {"status": "Status", "monthly": "Monthly"}[report]
    )
    assert sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*")) == before


def _write_workspace_configuration(vault: Path) -> None:
    vault.joinpath("work-tracking.yaml").write_text(
        """schema: work-tracking/v1
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
""",
        encoding="utf-8",
    )
