"""Tests for canonical agent-root resolution and marker validation."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from secret_agents_setup.root import RootResolutionError, resolve_agent_root
from secret_agents_setup.root_errors import (
    InvalidRootMarker,
    MissingRootEntry,
    MissingRootMarker,
    RootIdentityMismatch,
    RootMarkerNotObject,
    RootNotResolved,
    RootSchemaVersionMismatch,
)


def make_root(path: Path, *, identity: str = "handbag-secret-agents", schema_version: int = 1) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / ".agent-root.json").write_text(
        json.dumps({"identity": identity, "schema_version": schema_version}),
        encoding="utf-8",
    )
    (path / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    (path / "model-routing.json").write_text("{}\n", encoding="utf-8")
    (path / "skills").mkdir(exist_ok=True)
    (path / "runbooks").mkdir(exist_ok=True)
    return path


def _make_root_missing_entry(base: Path) -> Path:
    root = make_root(base)
    (root / "AGENTS.md").unlink()
    return root


def test_explicit_root_wins_over_environment(tmp_path: Path) -> None:
    explicit = make_root(tmp_path / "explicit")
    env_root = make_root(tmp_path / "env")
    result = resolve_agent_root(
        explicit=explicit,
        environment={"SECRET_AGENTS_ROOT": str(env_root)},
        script_path=tmp_path / "elsewhere" / "script.py",
    )
    assert result.path == explicit.resolve()


def test_environment_root_wins_over_self_location(tmp_path: Path) -> None:
    env_root = make_root(tmp_path / "env")
    ancestor_root = make_root(tmp_path / "ancestor")
    result = resolve_agent_root(
        explicit=None,
        environment={"SECRET_AGENTS_ROOT": str(env_root)},
        script_path=ancestor_root / "sub" / "script.py",
    )
    assert result.path == env_root.resolve()


def test_nearest_marker_ancestor_is_used(tmp_path: Path) -> None:
    outer = make_root(tmp_path / "outer")
    inner = make_root(outer / "inner")
    result = resolve_agent_root(
        explicit=None,
        environment={},
        script_path=inner / "scripts" / "harness_setup.py",
    )
    assert result.path == inner.resolve()


def test_missing_root_reports_all_supported_resolution_methods(tmp_path: Path) -> None:
    with pytest.raises(RootNotResolved) as excinfo:
        resolve_agent_root(
            explicit=None,
            environment={},
            script_path=tmp_path / "no_marker" / "deep" / "script.py",
        )
    message = str(excinfo.value)
    assert "--agent-root" in message
    assert "SECRET_AGENTS_ROOT" in message
    assert "marker" in message.lower()


@pytest.mark.parametrize(
    ("make_invalid", "error_type", "invariant"),
    [
        (lambda base: make_root(base, identity="not-ours"), RootIdentityMismatch, "identity"),
        (lambda base: make_root(base, schema_version=2), RootSchemaVersionMismatch, "schema_version"),
        (_make_root_missing_entry, MissingRootEntry, "AGENTS.md"),
    ],
)
def test_invalid_marker_is_rejected(
    tmp_path: Path,
    make_invalid: Callable[[Path], Path],
    error_type: type[RootResolutionError],
    invariant: str,
) -> None:
    root = make_invalid(tmp_path / "root")
    with pytest.raises(error_type) as excinfo:
        resolve_agent_root(
            explicit=root,
            environment={},
            script_path=tmp_path / "script.py",
        )
    message = str(excinfo.value)
    assert str(root.resolve()) in message
    assert invariant in message


def test_explicit_root_without_marker_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()

    with pytest.raises(MissingRootMarker):
        resolve_agent_root(root, {}, tmp_path / "script.py")


def test_invalid_marker_json_preserves_cause(tmp_path: Path) -> None:
    root = make_root(tmp_path / "root")
    (root / ".agent-root.json").write_text("not json", encoding="utf-8")

    with pytest.raises(InvalidRootMarker) as excinfo:
        resolve_agent_root(root, {}, tmp_path / "script.py")

    assert isinstance(excinfo.value.__cause__, json.JSONDecodeError)


def test_marker_must_contain_an_object(tmp_path: Path) -> None:
    root = make_root(tmp_path / "root")
    (root / ".agent-root.json").write_text("[]", encoding="utf-8")

    with pytest.raises(RootMarkerNotObject):
        resolve_agent_root(root, {}, tmp_path / "script.py")
