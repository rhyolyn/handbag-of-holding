"""Run configured Work Tracking reporting skills without scheduler setup."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from secret_agents_work_tracking.errors import WorkspaceError
from secret_agents_work_tracking.models import Workspace
from secret_agents_work_tracking.workspace import resolve_workspace


@dataclass(frozen=True)
class ReportRequest:
    """Describe one report skill and its resolver-owned output location."""

    skill: str
    output_location: Path


class ReportRunner:
    """Run report skills only after the selected workspace validates."""

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    def build_request(self, report: str) -> ReportRequest:
        """Choose the current skill and named output location for one report type."""
        if report == "status":
            return ReportRequest("/report-status", self.workspace.location("status_reports", require_exists=False))
        assert report == "monthly", f"Unsupported report: {report}"
        return ReportRequest(self._monthly_prompt(), self.workspace.location("monthly_reports", require_exists=False))

    def run(self, request: ReportRequest) -> int:
        """Invoke one current skill from the selected source vault."""
        return subprocess.run(
            ["claude", "-p", request.skill, "--permission-mode", "acceptEdits"],
            cwd=self.workspace.vault_root,
            check=False,
        ).returncode

    @staticmethod
    def _monthly_prompt() -> str:
        previous_month = date.today().replace(day=1) - timedelta(days=1)
        return f"/report-rollup month {previous_month:%Y-%m}"


def main(argv: list[str] | None = None) -> int:
    """Validate the selected workspace before checking or invoking one report skill."""
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    try:
        workspace = resolve_workspace(None, arguments.vault, {}, ROOT)
        request = ReportRunner(workspace).build_request(arguments.report)
    except WorkspaceError as exc:
        parser.error(str(exc))
    if arguments.check:
        print(json.dumps(_check_payload(workspace, request), indent=2))
        return 0
    return ReportRunner(workspace).run(request)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a configured Work Tracking report.")
    parser.add_argument("report", choices=("status", "monthly"))
    parser.add_argument("--vault", type=Path, help="Work Tracking vault; overrides environment selection.")
    parser.add_argument("--check", action="store_true", help="Validate configured locations without invoking a skill.")
    return parser


def _check_payload(workspace: Workspace, request: ReportRequest) -> dict[str, str]:
    return {
        "config_path": str(workspace.config_path),
        "output_location": str(request.output_location),
        "skill": request.skill.split(" ", maxsplit=1)[0],
        "vault": str(workspace.vault_root),
    }


if __name__ == "__main__":
    raise SystemExit(main())
