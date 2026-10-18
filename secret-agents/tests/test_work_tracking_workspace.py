"""Workspace configuration selection and containment contracts."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from secret_agents_work_tracking.errors import WorkspaceConfigurationError, WorkspaceLocationError
from secret_agents_work_tracking.workspace import resolve_workspace

DEFAULT_CONFIG = """\
schema: work-tracking/v1
tracking_root: Work Tracking
timezone: America/Los_Angeles
locations:
  receipts: Receipts
  daily_notes: Daily
  perforce_checkins: Checkins/perforce
  git_checkins: Checkins/git
  status_reports: Reports/Status
  monthly_reports: Reports/Monthly
  annual_reviews: Reports/Annual
  templates: Templates
  imports: Imports
  ledgers: Ledgers
"""


def test_explicit_config_overrides_explicit_vault_and_environment(tmp_path: Path) -> None:
    selected_vault = tmp_path / "selected"
    explicit_config = write_config(selected_vault)
    workspace = resolve_workspace(
        explicit_config,
        tmp_path / "ignored-vault",
        {"WORKY_WORKSPACE_CONFIG": str(write_config(tmp_path / "environment"))},
        tmp_path / "agent-root",
    )

    assert workspace.config_path == explicit_config
    assert workspace.vault_root == selected_vault


def test_explicit_vault_overrides_environment_configuration(tmp_path: Path) -> None:
    explicit_vault = tmp_path / "explicit"
    write_config(explicit_vault)
    workspace = resolve_workspace(
        None,
        explicit_vault,
        {"WORKY_WORKSPACE_CONFIG": str(write_config(tmp_path / "environment"))},
        tmp_path / "agent-root",
    )

    assert workspace.vault_root == explicit_vault


def test_environment_config_precedes_environment_vault(tmp_path: Path) -> None:
    configured_vault = tmp_path / "configured"
    environment_vault = tmp_path / "environment-vault"
    configured_path = write_config(configured_vault)
    write_config(environment_vault)

    workspace = resolve_workspace(
        None,
        None,
        {"WORKY_WORKSPACE_CONFIG": str(configured_path), "WORKY_VAULT_ROOT": str(environment_vault)},
        tmp_path / "agent-root",
    )

    assert workspace.config_path == configured_path
    assert workspace.vault_root == configured_vault


def test_environment_vault_precedes_agent_root_fallback(tmp_path: Path) -> None:
    environment_vault = tmp_path / "environment-vault"
    write_config(environment_vault)
    fallback_vault = tmp_path / "worky"
    write_config(fallback_vault)

    workspace = resolve_workspace(
        None,
        None,
        {"WORKY_VAULT_ROOT": str(environment_vault)},
        tmp_path / "handbag-of-holding" / "secret-agents",
    )

    assert workspace.vault_root == environment_vault


def test_agent_root_fallback_uses_only_sibling_worky_vault(tmp_path: Path) -> None:
    agent_root = tmp_path / "handbag-of-holding" / "secret-agents"
    fallback_vault = tmp_path / "worky"
    config_path = write_config(fallback_vault)

    workspace = resolve_workspace(None, None, {}, agent_root)

    assert workspace.config_path == config_path
    assert workspace.vault_root == fallback_vault
    assert workspace.tracking_root == fallback_vault / "Work Tracking"
    assert workspace.location("receipts", require_exists=False) == fallback_vault / "Work Tracking" / "Receipts"


def test_exact_v1_configuration_exposes_only_named_locations(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    write_config(vault)

    workspace = resolve_workspace(None, vault, {}, tmp_path / "agent-root")

    assert set(workspace.locations) == {
        "receipts",
        "daily_notes",
        "perforce_checkins",
        "git_checkins",
        "status_reports",
        "monthly_reports",
        "annual_reviews",
        "templates",
        "imports",
        "ledgers",
    }
    assert workspace.timezone.key == "America/Los_Angeles"


def test_workspace_locations_cannot_be_replaced_by_consumers(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    write_config(vault)
    workspace = resolve_workspace(None, vault, {}, tmp_path / "agent-root")
    locations = cast(dict[str, Path], workspace.locations)

    with pytest.raises(TypeError):
        locations["receipts"] = tmp_path / "replacement"


def test_missing_location_key_is_an_actionable_configuration_error(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    config_path = write_config(vault, DEFAULT_CONFIG.replace("  imports: Imports\n", ""))

    with pytest.raises(WorkspaceConfigurationError, match="imports"):
        resolve_workspace(config_path, None, {}, tmp_path / "agent-root")


def test_unknown_schema_is_an_actionable_configuration_error(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    config_path = write_config(vault, DEFAULT_CONFIG.replace("work-tracking/v1", "work-tracking/v2"))

    with pytest.raises(WorkspaceConfigurationError, match="work-tracking/v1"):
        resolve_workspace(config_path, None, {}, tmp_path / "agent-root")


@pytest.mark.parametrize("receipt_location", ["/outside", "../outside"])
def test_location_values_must_remain_relative_to_tracking_root(tmp_path: Path, receipt_location: str) -> None:
    vault = tmp_path / "vault"
    config_path = write_config(
        vault, DEFAULT_CONFIG.replace("  receipts: Receipts", f"  receipts: {receipt_location!r}")
    )

    with pytest.raises(WorkspaceConfigurationError, match="receipts"):
        resolve_workspace(config_path, None, {}, tmp_path / "agent-root")


def test_required_location_fails_without_creating_the_tracking_root(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    write_config(vault)
    workspace = resolve_workspace(None, vault, {}, tmp_path / "agent-root")

    with pytest.raises(WorkspaceLocationError, match="receipts"):
        workspace.location("receipts", require_exists=True)

    assert not workspace.tracking_root.exists()


def write_config(vault: Path, configuration: str = DEFAULT_CONFIG) -> Path:
    vault.mkdir()
    config_path = vault / "work-tracking.yaml"
    config_path.write_text(configuration, encoding="utf-8")
    return config_path
