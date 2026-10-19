"""Run Worky reporting skills from the consolidated agent vault.

Use --check to validate paths without invoking Claude or writing any files.
Worky data resolves from --vault, WORKY_VAULT_ROOT, or the sibling worky vault.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class ReportType:
    task: str
    prompt: str
    commit_message: str
    stage_paths: tuple[str, ...]
    produced_output: Callable[[], bool]


class ReportRunner:
    """Own the resolved Worky location and the reporting operations that use it."""

    def __init__(self, vault: Path) -> None:
        self.vault = vault.resolve()

    @property
    def dashboard(self) -> Path:
        return self.vault / "Dashboards/System Status.md"

    @property
    def log_directory(self) -> Path:
        return self.vault / "Scripts/logs"

    def build(self, report: str) -> ReportType:
        if report == "status":
            reports = self.vault / "Status Reports"
            before = self._count_reports(reports)
            return ReportType(
                task="status-report",
                prompt="/report-status",
                commit_message=f"Scheduled status report {date.today():%Y-%m-%d}",
                stage_paths=("Status Reports", "Receipts/cost-ledger.csv", "Dashboards/System Status.md"),
                produced_output=lambda: self._count_reports(reports) > before,
            )
        assert report == "monthly", f"Unsupported report: {report}"
        previous = date.today().replace(day=1) - timedelta(days=1)
        month = f"{previous:%Y-%m}"
        expected = self.vault / "Status Reports" / month[:4] / month / f"monthly-{month}.md"
        return ReportType(
            task="monthly-rollup",
            prompt=f"/report-rollup month {month}",
            commit_message=f"Scheduled monthly rollup {month}",
            stage_paths=("Status Reports", "Receipts/cost-ledger.csv"),
            produced_output=expected.exists,
        )

    def run(self, report: ReportType, dry_run: bool) -> int:
        self.log_directory.mkdir(parents=True, exist_ok=True)
        log_path = self.log_directory / f"{report.task}-{datetime.now():%Y-%m-%d-%H%M}.log"
        exit_code = self._invoke_claude(report.prompt, log_path)
        skipped = "already exists" in log_path.read_text(encoding="utf-8")
        if exit_code != 0 or not (report.produced_output() or skipped):
            self._update_status_line(report.task, f"FAILED (exit {exit_code}, see {log_path.name})")
            return 1
        if skipped:
            self._update_status_line(report.task, "success (skipped - already up to date)")
        elif dry_run:
            self._update_status_line(report.task, "success (dry-run, not committed)")
        elif self.is_git_root():
            self._commit(report)
        else:
            self._update_status_line(report.task, "success (synced vault; no git commit)")
        return 0

    def is_git_root(self) -> bool:
        # Do not stage Worky data into an enclosing, unrelated repository.
        if not (self.vault / ".git").exists():
            return False
        result = subprocess.run(
            ["git", "-C", str(self.vault), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip()).resolve() == self.vault

    def _invoke_claude(self, prompt: str, log_path: Path) -> int:
        result = subprocess.run(
            ["claude", "-p", prompt, "--permission-mode", "acceptEdits"],
            cwd=self.vault,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        log_path.write_text(result.stdout, encoding="utf-8")
        sys.stdout.write(result.stdout)
        return result.returncode

    def _commit(self, report: ReportType) -> None:
        self._git("add", *report.stage_paths)
        self._update_status_line(report.task, "success")
        self._git("add", "Dashboards/System Status.md")
        self._git("commit", "-m", report.commit_message)

    def _update_status_line(self, task: str, result: str) -> None:
        stamp = f"{datetime.now():%Y-%m-%d %H:%M}"
        new_line = f"- {task}: last run {stamp}, result: {result}"
        content = self.dashboard.read_text(encoding="utf-8")
        content = re.sub(rf"(?m)^- {re.escape(task)}:.*$", new_line, content)
        self.dashboard.write_text(content, encoding="utf-8", newline="")

    @staticmethod
    def _count_reports(root: Path) -> int:
        return sum(1 for _ in root.rglob("sr-*.md")) if root.exists() else 0

    def _git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.vault), *args], check=True)


def resolve_vault(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.expanduser().resolve()
    configured = os.environ.get("WORKY_VAULT_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[3] / "worky"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a scheduled Worky report.")
    parser.add_argument("report", choices=("status", "monthly"))
    parser.add_argument("--vault", type=Path, help="Worky data vault; overrides WORKY_VAULT_ROOT.")
    parser.add_argument("--check", action="store_true", help="Validate paths without generating or writing anything.")
    parser.add_argument(
        "--dry-run", action="store_true", help="Run the skill and write output, but skip the Git commit."
    )
    args = parser.parse_args(argv)
    vault = resolve_vault(args.vault)
    if not vault.is_dir():
        parser.error(f"data vault does not exist: {vault}")
    required = ["Dashboards/System Status.md", "Status Reports"]
    if args.report == "status":
        required.extend(["Receipts", "Templates/Status Report Template.md"])
    missing = [str(vault / relative) for relative in required if not (vault / relative).exists()]
    if missing:
        parser.error("required Worky inputs missing: " + ", ".join(missing))
    application = ReportRunner(vault)
    report = application.build(args.report)
    if args.check:
        print(
            json.dumps(
                {"vault": str(vault), "skill": report.prompt, "will_commit": application.is_git_root()}, indent=2
            )
        )
        return 0
    return application.run(report, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
