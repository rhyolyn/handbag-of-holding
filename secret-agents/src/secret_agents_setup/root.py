"""Canonical-root marker loading and resolution."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from .models import AgentRoot

MARKER_NAME = ".agent-root.json"
REQUIRED_IDENTITY = "handbag-secret-agents"
REQUIRED_SCHEMA_VERSION = 1
REQUIRED_ENTRIES = ("AGENTS.md", "model-routing.json", "skills", "runbooks")


class RootResolutionError(Exception):
    """Raised when the canonical agent root cannot be resolved or validated."""


def resolve_agent_root(
    explicit: Path | None,
    environment: Mapping[str, str],
    script_path: Path,
) -> AgentRoot:
    """Resolve the canonical root by explicit path, environment, then marker ancestry."""
    if explicit is not None:
        return _validate_root(explicit.resolve())

    env_value = environment.get("SECRET_AGENTS_ROOT")
    if env_value:
        return _validate_root(Path(env_value).resolve())

    start = script_path.resolve()
    for candidate in (start, *start.parents):
        if (candidate / MARKER_NAME).is_file():
            try:
                return _validate_root(candidate)
            except RootResolutionError:
                continue

    raise RootResolutionError(
        "Could not resolve the canonical agent root. Pass it explicitly with --agent-root, "
        "set the SECRET_AGENTS_ROOT environment variable, or run from a checkout whose "
        f"ancestor contains a valid {MARKER_NAME} marker."
    )


def _validate_root(path: Path) -> AgentRoot:
    marker = path / MARKER_NAME
    if not marker.is_file():
        raise RootResolutionError(f"{path}: missing {MARKER_NAME} marker")

    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RootResolutionError(f"{path}: unreadable or invalid {MARKER_NAME} ({exc})") from exc

    if not isinstance(data, dict):
        raise RootResolutionError(f"{path}: {MARKER_NAME} must contain a JSON object")

    identity = data.get("identity")
    if identity != REQUIRED_IDENTITY:
        raise RootResolutionError(
            f"{path}: identity must be {REQUIRED_IDENTITY!r}, found {identity!r}"
        )

    schema_version = data.get("schema_version")
    if schema_version != REQUIRED_SCHEMA_VERSION:
        raise RootResolutionError(
            f"{path}: schema_version must be {REQUIRED_SCHEMA_VERSION}, found {schema_version!r}"
        )

    for entry in REQUIRED_ENTRIES:
        if not (path / entry).exists():
            raise RootResolutionError(f"{path}: missing required entry {entry!r}")

    return AgentRoot(path=path, schema_version=schema_version, identity=identity)
