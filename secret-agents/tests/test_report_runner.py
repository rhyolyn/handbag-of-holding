"""Report automation must keep its data in Worky after moving the runner."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_report.py"


@pytest.fixture
def runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("report_runner_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_default_data_vault_is_sibling_of_handbag(runner: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WORKY_VAULT_ROOT", raising=False)
    assert runner.resolve_vault(None) == ROOT.parents[1] / "worky"


def test_explicit_data_vault_overrides_environment(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WORKY_VAULT_ROOT", str(tmp_path / "environment"))
    assert runner.resolve_vault(tmp_path / "explicit") == tmp_path / "explicit"
    assert runner.resolve_vault(None) == tmp_path / "environment"


def test_check_does_not_create_a_missing_vault(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "status", "--check", "--vault", str(missing)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "data vault does not exist" in result.stderr
    assert not missing.exists()


@pytest.mark.parametrize("report", ["status", "monthly"])
def test_check_has_no_generation_or_filesystem_side_effects(report: str, tmp_path: Path) -> None:
    (tmp_path / "Dashboards").mkdir()
    (tmp_path / "Dashboards/System Status.md").write_text("# Status\n")
    (tmp_path / "Templates").mkdir()
    (tmp_path / "Templates/Status Report Template.md").write_text("# Report\n")
    (tmp_path / "Receipts").mkdir()
    (tmp_path / "Status Reports").mkdir()
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
    assert data["will_commit"] is False
    assert data["skill"].startswith("/report-")
    assert sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*")) == before


@pytest.mark.parametrize("parent_is_repository", [False, True])
def test_successful_report_in_synced_vault_does_not_require_git(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, parent_is_repository: bool
) -> None:
    if parent_is_repository:
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True, check=True)
    vault = tmp_path / "worky"
    dashboard = vault / "Dashboards/System Status.md"
    dashboard.parent.mkdir(parents=True)
    dashboard.write_text("# Status\n- status-report: pending\n", encoding="utf-8")
    application = runner.ReportRunner(vault)
    output = vault / "Status Reports/report.md"

    def generate_report(prompt: str, log_path: Path) -> int:
        output.parent.mkdir()
        output.write_text("# Generated report\n")
        log_path.write_text("Generated report\n")
        return 0

    monkeypatch.setattr(application, "_invoke_claude", generate_report)
    report = runner.ReportType("status-report", "/report-status", "Report", ("Status Reports",), output.exists)
    assert application.run(report, dry_run=False) == 0
    assert output.read_text() == "# Generated report\n"
    assert "success (synced vault; no git commit)" in dashboard.read_text()
    if parent_is_repository:
        assert not (tmp_path / ".git/index").exists()
