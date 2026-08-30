"""Argument parsing, orchestration, stable output, and exit codes."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from pathlib import Path

from .catalog import load_skill_catalog
from .catalog_errors import SkillCatalogError
from .executor import apply_install_plan, apply_uninstall_plan
from .executor_errors import BackupPathOccupied, ExecutionError
from .harness_profiles import build_projections
from .link_errors import SymlinkPrivilegeRequired, SymlinkUnsupported
from .links import LinkBackend, backend_for
from .models import (
    ActionKind,
    AgentRoot,
    ExecutionReport,
    Finding,
    Harness,
    InstallPlan,
    Projection,
    SkillDescriptor,
    UninstallFinding,
)
from .planning import build_install_plan, build_uninstall_plan
from .receipt_errors import ReceiptError
from .receipts import load_receipt, receipt_path
from .root import resolve_agent_root
from .root_errors import RootResolutionError

_CAPABILITY_NOTE = "note capability-unverified-until-install"


class ExitCode(IntEnum):
    SUCCESS = 0
    INVALID_INPUT = 2
    BLOCKED = 3
    EXECUTION_FAILED = 4


def main(
    argv: Sequence[str] | None = None,
    *,
    environment: Mapping[str, str] | None = None,
    home: Path | None = None,
    script_path: Path | None = None,
    os_name: str | None = None,
    now: Callable[[], datetime] | None = None,
    backend: LinkBackend | None = None,
) -> int:
    """Resolve, plan, and apply the requested harness-setup command; return an exit code."""
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        return _exit_code_from(exc)

    try:
        session = _open_session(args, environment, home, script_path, os_name, now, backend)
    except (RootResolutionError, SkillCatalogError) as exc:
        _err(str(exc))
        return ExitCode.INVALID_INPUT

    _print(f"root {session.root.path}")
    _print(f"harness {args.harness}")
    if args.command == "check":
        return _run_check(session)
    if args.command == "install":
        return _run_install(session, args)
    return _run_uninstall(session)


def _run_check(session: _Session) -> int:
    plan = session.install_plan(backup_conflicts=False)
    _print_findings(plan.findings)
    _note_windows_capability(session, plan)
    if plan.can_apply and not plan.actions:
        return _ok()
    return _blocked("remediation required: run 'install' to create or repair the reported projections")


def _run_install(session: _Session, args: argparse.Namespace) -> int:
    plan = session.install_plan(backup_conflicts=args.backup_conflicts)
    _print_findings(plan.findings)

    if args.dry_run:
        _note_windows_capability(session, plan)
        return _ok() if plan.can_apply else _silent_blocked()
    if not plan.can_apply:
        return _blocked("install plan has blocking conditions; no changes were made")
    return _apply_install(session, plan)


def _run_uninstall(session: _Session) -> int:
    receipt_file = session.receipt_file
    try:
        receipt = load_receipt(receipt_file, expected_identity=session.identity, home=session.home)
    except ReceiptError as exc:
        return _blocked(str(exc))

    plan = build_uninstall_plan(
        receipt, session.harnesses, session.link_backend, expected_identity=session.identity, home=session.home
    )
    _print_findings(plan.findings)
    if not plan.can_apply:
        return _blocked("uninstall plan has blocking conditions; no changes were made")

    try:
        report = apply_uninstall_plan(plan, session.link_backend, receipt_file)
    except ExecutionError as exc:
        return _failed(str(exc))
    _print_events(report)
    return _not_installed() if _is_noop(report) else _ok()


def _apply_install(session: _Session, plan: InstallPlan) -> int:
    session.home.mkdir(parents=True, exist_ok=True)
    try:
        existing = load_receipt(session.receipt_file, expected_identity=session.identity, home=session.home)
        report = apply_install_plan(
            plan, session.root, session.home, session.link_backend, session.receipt_file, existing
        )
    except (BackupPathOccupied, ReceiptError, SymlinkPrivilegeRequired, SymlinkUnsupported) as exc:
        return _blocked(str(exc))
    except ExecutionError as exc:
        return _failed(str(exc))
    _print_events(report)
    return _ok()


@dataclass(frozen=True)
class _Session:
    """The resolved inputs every command shares, gathered once at startup."""

    root: AgentRoot
    catalog: tuple[SkillDescriptor, ...]
    projections: tuple[Projection, ...]
    harnesses: tuple[Harness, ...]
    home: Path
    os_name: str
    now: Callable[[], datetime]
    backend: LinkBackend | None

    @property
    def identity(self) -> str:
        return self.root.identity

    @property
    def receipt_file(self) -> Path:
        return receipt_path(self.home, self.identity)

    @property
    def link_backend(self) -> LinkBackend:
        return self.backend or backend_for(self.os_name)

    def install_plan(self, *, backup_conflicts: bool) -> InstallPlan:
        return build_install_plan(self.projections, self.catalog, backup_conflicts, self.now())


def _open_session(
    args: argparse.Namespace,
    environment: Mapping[str, str] | None,
    home: Path | None,
    script_path: Path | None,
    os_name: str | None,
    now: Callable[[], datetime] | None,
    backend: LinkBackend | None,
) -> _Session:
    environment = os.environ if environment is None else environment
    home = Path.home() if home is None else home
    script_path = Path(__file__) if script_path is None else script_path
    root = resolve_agent_root(args.agent_root, environment, script_path)
    catalog = load_skill_catalog(root.path / "skills")
    harnesses = _harness_selection(args.harness)
    return _Session(
        root=root,
        catalog=catalog,
        projections=build_projections(root, home, harnesses),
        harnesses=harnesses,
        home=home,
        os_name=os.name if os_name is None else os_name,
        now=_default_now if now is None else now,
        backend=backend,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness_setup", description="Project shared agent guidance and skills.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("install", "check", "uninstall"):
        sub = subcommands.add_parser(name)
        sub.add_argument("--harness", choices=["codex", "claude", "copilot", "all"], default="all")
        sub.add_argument("--agent-root", type=Path, default=None)
        if name == "install":
            sub.add_argument("--dry-run", action="store_true")
            sub.add_argument("--backup-conflicts", action="store_true")
    return parser


def _harness_selection(selector: str) -> tuple[Harness, ...]:
    if selector == "all":
        return (Harness.ALL,)
    return (Harness(selector),)


def _note_windows_capability(session: _Session, plan: InstallPlan) -> None:
    link_actions = (ActionKind.CREATE_LINK, ActionKind.REPLACE_LINK)
    needs_file_link = any(action.kind in link_actions and not action.is_directory for action in plan.actions)
    if session.os_name == "nt" and needs_file_link:
        _print(_CAPABILITY_NOTE)


def _is_noop(report: ExecutionReport) -> bool:
    return report.receipt is None and not report.events


def _print_findings(findings: Sequence[Finding | UninstallFinding]) -> None:
    for finding in findings:
        _print(f"finding {finding.state.value} {finding.path}")


def _print_events(report: ExecutionReport) -> None:
    for event in report.events:
        _print(f"did {event.kind.value} {event.path}")


def _ok() -> int:
    _print("result ok")
    return ExitCode.SUCCESS


def _not_installed() -> int:
    _print("result not-installed")
    return ExitCode.SUCCESS


def _blocked(reason: str) -> int:
    _print("result blocked")
    _err(reason)
    return ExitCode.BLOCKED


def _silent_blocked() -> int:
    _print("result blocked")
    return ExitCode.BLOCKED


def _failed(reason: str) -> int:
    _print("result failed")
    _err(reason)
    return ExitCode.EXECUTION_FAILED


def _exit_code_from(exc: SystemExit) -> int:
    code = exc.code
    if code is None:
        return int(ExitCode.SUCCESS)
    if isinstance(code, int):
        return code
    return int(ExitCode.INVALID_INPUT)


def _default_now() -> datetime:
    return datetime.now()


def _print(message: str) -> None:
    print(message, file=sys.stdout)


def _err(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
