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
from .executor import AppliedChange, UninstallResultState, apply_install_plan, apply_uninstall_plan
from .executor_errors import BackupPathOccupied, ExecutionError
from .harness_profiles import InstallMapping, InstructionsMapping, build_install_mappings
from .link_errors import SymlinkPrivilegeRequired, SymlinkUnsupported
from .links import LinkBackend, backend_for
from .models import (
    AgentRoot,
    Harness,
    SkillDescriptor,
)
from .planning import (
    CreateLink,
    InstallPlan,
    PathStatus,
    RemovalStatus,
    ReplaceLink,
    build_install_plan,
    build_uninstall_plan,
)
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
    _print_statuses(plan.statuses)
    _note_windows_capability(session, plan)
    if not plan.is_blocked and not plan.changes:
        return _ok()
    return _blocked("remediation required: run 'install' to create or repair the reported projections")


def _run_install(session: _Session, args: argparse.Namespace) -> int:
    plan = session.install_plan(backup_conflicts=args.backup_conflicts)
    _print_statuses(plan.statuses)

    if args.dry_run:
        _note_windows_capability(session, plan)
        return _silent_blocked() if plan.is_blocked else _ok()
    if plan.is_blocked:
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
    _print_removal_statuses(plan.statuses)
    if plan.is_blocked:
        return _blocked("uninstall plan has blocking conditions; no changes were made")

    try:
        result = apply_uninstall_plan(plan, session.link_backend)
    except ExecutionError as exc:
        return _failed(str(exc))
    _print_applied(result.changes)
    if result.state is UninstallResultState.NOT_INSTALLED:
        return _not_installed()
    return _ok()


def _apply_install(session: _Session, plan: InstallPlan) -> int:
    session.home.mkdir(parents=True, exist_ok=True)
    try:
        existing = load_receipt(session.receipt_file, expected_identity=session.identity, home=session.home)
        result = apply_install_plan(
            plan, session.root, session.home, session.link_backend, session.receipt_file, existing
        )
    except (BackupPathOccupied, ReceiptError, SymlinkPrivilegeRequired, SymlinkUnsupported) as exc:
        return _blocked(str(exc))
    except ExecutionError as exc:
        return _failed(str(exc))
    _print_applied(result.changes)
    return _ok()


@dataclass(frozen=True)
class _Session:
    """The resolved inputs every command shares, gathered once at startup."""

    root: AgentRoot
    catalog: tuple[SkillDescriptor, ...]
    mappings: tuple[InstallMapping, ...]
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
        return build_install_plan(self.mappings, self.catalog, backup_conflicts, self.now())


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
        mappings=build_install_mappings(root, home, harnesses),
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
    needs_file_link = any(
        isinstance(change, (CreateLink, ReplaceLink)) and isinstance(change.mapping, InstructionsMapping)
        for change in plan.changes
    )
    if session.os_name == "nt" and needs_file_link:
        _print(_CAPABILITY_NOTE)


def _print_statuses(statuses: Sequence[PathStatus]) -> None:
    for status in statuses:
        _print(f"finding {status.state.output_name} {status.path}")


def _print_removal_statuses(statuses: Sequence[RemovalStatus]) -> None:
    for status in statuses:
        _print(f"finding {status.state.value} {status.path}")


def _print_applied(changes: Sequence[AppliedChange]) -> None:
    for change in changes:
        _print(f"did {change.operation.value} {change.path}")


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
