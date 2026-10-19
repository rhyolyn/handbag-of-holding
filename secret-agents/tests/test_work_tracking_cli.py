"""The work-tracking command boundary validates without creating workspace paths."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
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


def test_workspace_check_writes_json_without_creating_paths(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    config_path = vault / "work-tracking.yaml"
    config_path.write_text(CONFIGURATION, encoding="utf-8")
    before = sorted(path.relative_to(vault) for path in vault.rglob("*"))

    result = subprocess.run(
        [sys.executable, "-m", "secret_agents_work_tracking", "workspace", "check", "--config", str(config_path)],
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=command_environment(),
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = cast(dict[str, object], json.loads(result.stdout))
    assert payload["config_path"] == str(config_path)
    assert payload["tracking_root"] == str(vault / "Work Tracking")
    assert sorted(path.relative_to(vault) for path in vault.rglob("*")) == before


def command_environment() -> dict[str, str]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    return environment
