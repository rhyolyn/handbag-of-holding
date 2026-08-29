"""Argument parsing, orchestration, stable output, and exit codes."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from enum import IntEnum
from pathlib import Path

from .catalog import load_skill_catalog
from .catalog_errors import SkillCatalogError
from .executor import apply_install_plan, apply_uninstall_plan
from .executor_errors import ExecutionError
from .harness_profiles import build_projections
from .link_errors import SymlinkPrivilegeRequired, SymlinkUnsupported
from .links import LinkBackend, backend_for
from .models import (
    ActionKind,
    AgentRoot,
    ExecutionReport,
    Harness,
    InstallPlan,
    Projection,
    SkillDescriptor,
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
    environment = os.environ if environment is None else environment
    home = Path.home() if home is None else home
    script_path = Path(__file__) if script_path is None else script_path
    os_name = os.name if os_name is None else os_name
    now = _default_now if now is None else now

    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        return _exit_code_from(exc)

    try:
        root = resolve_agent_root(args.agent_root, environment, script_path)
        catalog = load_skill_catalog(root.path / "skills")
    except (RootResolutionError, SkillCatalogError) as exc:
        _err(str(exc))
        return ExitCode.INVALID_INPUT

    harnesses = _harness_selection(args.harness)
    projections = build_projections(root, home, harnesses)
    _print(f"root {root.path}")
    _print(f"harness {args.harness}")

    if args.command == "check":
        return _run_check(projections, catalog, os_name, now)
    if args.command == "install":
        return _run_install(args, projections, catalog, root, home, os_name, now, backend)
    return _run_uninstall(root, home, harnesses, os_name, backend)


def _run_check(
    projections: tuple[Projection, ...],
    catalog: tuple[SkillDescriptor, ...],
    os_name: str,
    now: Callable[[], datetime],
) -> int:
    plan = build_install_plan(projections, catalog, False, now())
    _print_findings(plan)
    if os_name == "nt" and _has_file_link_action(plan):
        _print(_CAPABILITY_NOTE)
    if plan.can_apply and not plan.actions:
        _print("result ok")
        return ExitCode.SUCCESS
    _print("result blocked")
    _err("remediation required: run 'install' to create or repair the reported projections")
    return ExitCode.BLOCKED


def _run_install(
    args: argparse.Namespace,
    projections: tuple[Projection, ...],
    catalog: tuple[SkillDescriptor, ...],
    root: AgentRoot,
    home: Path,
    os_name: str,
    now: Callable[[], datetime],
    backend: LinkBackend | None,
) -> int:
    plan = build_install_plan(projections, catalog, args.backup_conflicts, now())
    _print_findings(plan)

    if args.dry_run:
        if os_name == "nt" and _has_file_link_action(plan):
            _print(_CAPABILITY_NOTE)
        if plan.can_apply:
            _print("result ok")
            return ExitCode.SUCCESS
        _print("result blocked")
        return ExitCode.BLOCKED

    if not plan.can_apply:
        _print("result blocked")
        _err("install plan has blocking conditions; no changes were made")
        return ExitCode.BLOCKED

    backend = backend or backend_for(os_name)
    receipt_file = receipt_path(home, root.identity)
    home.mkdir(parents=True, exist_ok=True)
    try:
        existing = load_receipt(receipt_file, expected_identity=root.identity, home=home)
    except ReceiptError as exc:
        _print("result blocked")
        _err(str(exc))
        return ExitCode.BLOCKED

    try:
        report = apply_install_plan(plan, root, home, backend, receipt_file, existing)
    except (SymlinkPrivilegeRequired, SymlinkUnsupported) as exc:
        _print("result blocked")
        _err(str(exc))
        return ExitCode.BLOCKED
    except ExecutionError as exc:
        _print("result failed")
        _err(str(exc))
        return ExitCode.EXECUTION_FAILED

    _print_events(report)
    _print("result ok")
    return ExitCode.SUCCESS


def _run_uninstall(
    root: AgentRoot,
    home: Path,
    harnesses: tuple[Harness, ...],
    os_name: str,
    backend: LinkBackend | None,
) -> int:
    backend = backend or backend_for(os_name)
    receipt_file = receipt_path(home, root.identity)
    try:
        receipt = load_receipt(receipt_file, expected_identity=root.identity, home=home)
    except ReceiptError as exc:
        _print("result blocked")
        _err(str(exc))
        return ExitCode.BLOCKED

    plan = build_uninstall_plan(receipt, harnesses, backend, expected_identity=root.identity, home=home)
    for finding in plan.findings:
        _print(f"finding {finding.state.value} {finding.path}")

    if not plan.can_apply:
        _print("result blocked")
        _err("uninstall plan has blocking conditions; no changes were made")
        return ExitCode.BLOCKED

    try:
        report = apply_uninstall_plan(plan, backend, receipt_file)
    except ExecutionError as exc:
        _print("result failed")
        _err(str(exc))
        return ExitCode.EXECUTION_FAILED

    _print_events(report)
    if report.receipt is None and not report.events:
        _print("result not-installed")
    else:
        _print("result ok")
    return ExitCode.SUCCESS


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


def _has_file_link_action(plan: InstallPlan) -> bool:
    link_actions = (ActionKind.CREATE_LINK, ActionKind.REPLACE_LINK)
    return any(action.kind in link_actions and not action.is_directory for action in plan.actions)


def _print_findings(plan: InstallPlan) -> None:
    for finding in plan.findings:
        _print(f"finding {finding.state.value} {finding.path}")


def _print_events(report: ExecutionReport) -> None:
    for event in report.events:
        _print(f"did {event.kind.value} {event.path}")


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
