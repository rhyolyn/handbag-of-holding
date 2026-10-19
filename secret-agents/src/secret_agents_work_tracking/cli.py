"""Read-only command boundary for validating a work-tracking workspace."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from .errors import WorkspaceError
from .models import Workspace
from .workspace import resolve_workspace


def main(argv: Sequence[str] | None = None, *, environment: Mapping[str, str] | None = None) -> int:
    """Validate the requested workspace and return a stable process exit code."""
    arguments = _build_parser().parse_args(argv)
    selected_environment = os.environ if environment is None else environment
    try:
        workspace = resolve_workspace(
            arguments.config, arguments.vault, selected_environment, _agent_root(selected_environment)
        )
    except WorkspaceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(_workspace_payload(workspace), sort_keys=True))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="secret_agents_work_tracking")
    workspace = parser.add_subparsers(dest="command", required=True).add_parser("workspace")
    check = workspace.add_subparsers(dest="workspace_command", required=True).add_parser("check")
    source = check.add_mutually_exclusive_group()
    source.add_argument("--config", type=Path)
    source.add_argument("--vault", type=Path)
    return parser


def _agent_root(environment: Mapping[str, str]) -> Path:
    configured_root = environment.get("SECRET_AGENTS_ROOT")
    if configured_root is not None:
        return Path(configured_root)
    return Path.home() / "obsidian" / "handbag-of-holding" / "secret-agents"


def _workspace_payload(workspace: Workspace) -> dict[str, object]:
    return {
        "config_path": str(workspace.config_path),
        "locations": {name: str(path) for name, path in workspace.locations.items()},
        "tracking_root": str(workspace.tracking_root),
        "vault_root": str(workspace.vault_root),
        "timezone": workspace.timezone.key,
    }
