"""Canonical-root marker loading and resolution."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from .models import AgentRoot
from .root_errors import (
    InvalidRootMarker,
    MissingRootEntry,
    MissingRootMarker,
    RootIdentityMismatch,
    RootMarkerNotObject,
    RootNotResolved,
    RootSchemaVersionMismatch,
)
from .root_errors import RootResolutionError as RootResolutionError

MARKER_NAME = ".agent-root.json"
REQUIRED_IDENTITY = "handbag-secret-agents"
REQUIRED_SCHEMA_VERSION = 1
REQUIRED_ENTRIES = ("AGENTS.md", "model-routing.json", "skills", "runbooks")


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

    raise RootNotResolved(MARKER_NAME)


def _validate_root(path: Path) -> AgentRoot:
    marker = path / MARKER_NAME
    if not marker.is_file():
        raise MissingRootMarker(path, MARKER_NAME)

    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InvalidRootMarker(path, MARKER_NAME, exc) from exc

    if not isinstance(data, dict):
        raise RootMarkerNotObject(path, MARKER_NAME)

    identity = data.get("identity")
    if identity != REQUIRED_IDENTITY:
        raise RootIdentityMismatch(path, REQUIRED_IDENTITY, identity)

    schema_version = data.get("schema_version")
    if schema_version != REQUIRED_SCHEMA_VERSION:
        raise RootSchemaVersionMismatch(path, REQUIRED_SCHEMA_VERSION, schema_version)

    for entry in REQUIRED_ENTRIES:
        if not (path / entry).exists():
            raise MissingRootEntry(path, entry)

    return AgentRoot(path=path, schema_version=schema_version, identity=identity)
