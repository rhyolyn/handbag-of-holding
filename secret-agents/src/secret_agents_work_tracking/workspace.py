"""Configuration precedence and safe path resolution for work tracking."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Final, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from .errors import WorkspaceConfigurationError
from .models import LocationName, Workspace

_CONFIGURATION_NAME: Final = "work-tracking.yaml"
_SCHEMA: Final = "work-tracking/v1"
_TRACKING_ROOT: Final = "Work Tracking"
_TIMEZONE: Final = "America/Los_Angeles"
_LOCATION_NAMES: Final[tuple[LocationName, ...]] = (
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
)


def resolve_workspace(
    explicit_config: Path | None,
    explicit_vault: Path | None,
    environment: Mapping[str, str],
    agent_root: Path,
) -> Workspace:
    """Select, validate, and resolve the one workspace used by this invocation."""
    config_path, vault_root = _select_workspace_paths(explicit_config, explicit_vault, environment, agent_root)
    data = _load_configuration(config_path)
    _validate_configuration_keys(config_path, data)
    _validate_schema(config_path, data)
    tracking_root = _resolve_tracking_root(config_path, vault_root, data)
    timezone = _resolve_timezone(config_path, data)
    locations = _resolve_locations(config_path, tracking_root, data)
    return Workspace(config_path, vault_root, tracking_root, timezone, locations)


def _select_workspace_paths(
    explicit_config: Path | None,
    explicit_vault: Path | None,
    environment: Mapping[str, str],
    agent_root: Path,
) -> tuple[Path, Path]:
    if explicit_config is not None:
        return _paths_for_config(explicit_config)
    if explicit_vault is not None:
        return _paths_for_vault(explicit_vault)
    if configured_path := environment.get("WORKY_WORKSPACE_CONFIG"):
        return _paths_for_config(Path(configured_path))
    if vault_root := environment.get("WORKY_VAULT_ROOT"):
        return _paths_for_vault(Path(vault_root))
    return _paths_for_vault(agent_root / ".." / ".." / "worky")


def _paths_for_config(config_path: Path) -> tuple[Path, Path]:
    resolved_config = config_path.resolve()
    return resolved_config, resolved_config.parent


def _paths_for_vault(vault_root: Path) -> tuple[Path, Path]:
    resolved_vault = vault_root.resolve()
    config_path = resolved_vault / _CONFIGURATION_NAME
    if config_path.resolve().parent != resolved_vault:
        raise WorkspaceConfigurationError(config_path, "configuration file must remain inside the selected vault")
    return config_path, resolved_vault


def _load_configuration(config_path: Path) -> Mapping[str, object]:
    if not config_path.is_file():
        raise WorkspaceConfigurationError(config_path, "configuration file is missing")
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        raise WorkspaceConfigurationError(config_path, f"configuration is unreadable ({exc})") from exc
    if not isinstance(data, dict):
        raise WorkspaceConfigurationError(config_path, "configuration must contain a mapping")
    return cast(Mapping[str, object], data)


def _resolve_tracking_root(config_path: Path, vault_root: Path, data: Mapping[str, object]) -> Path:
    value = _required_string(config_path, data, "tracking_root")
    if value != _TRACKING_ROOT:
        raise WorkspaceConfigurationError(config_path, f"tracking_root must be {_TRACKING_ROOT!r}")
    return _resolve_child(config_path, vault_root, value, "tracking_root")


def _validate_schema(config_path: Path, data: Mapping[str, object]) -> None:
    value = _required_string(config_path, data, "schema")
    if value != _SCHEMA:
        raise WorkspaceConfigurationError(config_path, f"schema must be {_SCHEMA!r}")


def _validate_configuration_keys(config_path: Path, data: Mapping[str, object]) -> None:
    allowed_keys = {"schema", "tracking_root", "timezone", "locations"}
    unknown_keys = set(data) - allowed_keys
    if unknown_keys:
        names = ", ".join(sorted(str(key) for key in unknown_keys))
        raise WorkspaceConfigurationError(config_path, f"configuration contains unknown keys: {names}")


def _resolve_timezone(config_path: Path, data: Mapping[str, object]) -> ZoneInfo:
    value = _required_string(config_path, data, "timezone")
    if value != _TIMEZONE:
        raise WorkspaceConfigurationError(config_path, f"timezone must be {_TIMEZONE!r}")
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise WorkspaceConfigurationError(config_path, f"timezone {value!r} is unavailable") from exc


def _resolve_locations(config_path: Path, tracking_root: Path, data: Mapping[str, object]) -> dict[LocationName, Path]:
    raw_locations = data.get("locations")
    if not isinstance(raw_locations, dict):
        raise WorkspaceConfigurationError(config_path, "locations must contain a mapping")
    missing = set(_LOCATION_NAMES) - set(raw_locations)
    extra = set(raw_locations) - set(_LOCATION_NAMES)
    if missing or extra:
        raise WorkspaceConfigurationError(config_path, _location_key_reason(missing, extra))
    return {
        name: _resolve_child(config_path, tracking_root, _location_value(config_path, raw_locations, name), name)
        for name in _LOCATION_NAMES
    }


def _required_string(config_path: Path, data: Mapping[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise WorkspaceConfigurationError(config_path, f"{key} must be a non-empty string")
    return value


def _location_value(config_path: Path, locations: Mapping[object, object], name: LocationName) -> str:
    value = locations[name]
    if not isinstance(value, str) or not value:
        raise WorkspaceConfigurationError(config_path, f"{name} location must be a non-empty string")
    return value


def _location_key_reason(missing: Collection[str], extra: Collection[object]) -> str:
    parts = []
    if missing:
        parts.append(f"locations missing required keys: {', '.join(sorted(missing))}")
    if extra:
        parts.append(f"locations contains unknown keys: {', '.join(sorted(str(key) for key in extra))}")
    return "; ".join(parts)


def _resolve_child(config_path: Path, parent: Path, value: str, field_name: str) -> Path:
    relative_path = Path(value)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise WorkspaceConfigurationError(config_path, f"{field_name} must remain relative to its parent directory")
    path = (parent / relative_path).resolve()
    try:
        path.relative_to(parent.resolve())
    except ValueError as exc:
        raise WorkspaceConfigurationError(config_path, f"{field_name} escapes its parent directory") from exc
    return path
