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
        home=tmp_path / "home",
    )
    assert result.path == explicit.resolve()


def test_environment_root_wins_over_home_default(tmp_path: Path) -> None:
    env_root = make_root(tmp_path / "env")
    home = tmp_path / "home"
    make_root(home / "obsidian" / "handbag-of-holding" / "secret-agents")
    result = resolve_agent_root(
        explicit=None,
        environment={"SECRET_AGENTS_ROOT": str(env_root)},
        home=home,
    )
    assert result.path == env_root.resolve()


@pytest.mark.parametrize("home_name", ["alice", "User With Spaces", "Zoë"])
def test_home_default_ignores_checkout_and_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, home_name: str
) -> None:
    home = tmp_path / home_name
    expected = make_root(home / "obsidian" / "handbag-of-holding" / "secret-agents")
    old_checkout = make_root(tmp_path / "old-checkout")
    monkeypatch.chdir(old_checkout)
    assert resolve_agent_root(None, {}, home).path == expected.resolve()


def test_missing_home_source_reports_path_and_remediation_without_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_checkout = make_root(tmp_path / "old-checkout")
    monkeypatch.chdir(old_checkout)
    home = tmp_path / "home"
    with pytest.raises(MissingRootMarker) as excinfo:
        resolve_agent_root(None, {}, home)
    message = str(excinfo.value)
    assert str(home / "obsidian" / "handbag-of-holding" / "secret-agents") in message
    assert "--agent-root" in message
    assert "SECRET_AGENTS_ROOT" in message
    assert "marker" in message.lower()


def test_invalid_home_source_does_not_fall_back(tmp_path: Path) -> None:
    home = tmp_path / "home"
    make_root(home / "obsidian" / "handbag-of-holding" / "secret-agents", identity="wrong")
    with pytest.raises(RootIdentityMismatch):
        resolve_agent_root(None, {}, home)


@pytest.mark.parametrize("override", ["explicit", "environment"])
def test_tilde_override_expands_user_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, override: str) -> None:
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    expected = make_root(tmp_path / "custom source")
    explicit = Path("~/custom source") if override == "explicit" else None
    environment = {"SECRET_AGENTS_ROOT": "~/custom source"} if override == "environment" else {}
    assert resolve_agent_root(explicit, environment, tmp_path).path == expected.resolve()


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
            home=tmp_path,
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
