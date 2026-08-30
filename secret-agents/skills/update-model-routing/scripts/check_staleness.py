#!/usr/bin/env python3
"""Deterministic staleness checker for the centralized model-routing reference.

Reads ``model-routing.json`` without any network access and reports whether its
``last_verified`` date is still current. Standard library only.

Exit codes:
    0  reference is current (age <= stale_after_days)
    2  reference is malformed, invalid, or dated in the future
    3  reference is stale (age > stale_after_days)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

REQUIRED_PROVIDERS = ("codex", "claude")
REQUIRED_PROFILES = ("high-risk", "balanced", "routine", "economy")


class InvalidReferenceError(ValueError):
    """Raised when the routing reference is malformed, incomplete, or future-dated."""


@dataclass(frozen=True)
class StalenessReport:
    last_verified: date
    today: date
    age_days: int
    stale_after_days: int
    is_stale: bool


def routing_age_days(last_verified: date, today: date) -> int:
    return (today - last_verified).days


def _require_mapping(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise InvalidReferenceError(f"{path}: expected an object")
    return value


def _require_field(mapping: dict[str, object], key: str, path: str) -> object:
    if key not in mapping:
        raise InvalidReferenceError(f"{path}.{key}: missing required field")
    return mapping[key]


def _validate_sources(sources: object) -> None:
    mapping = _require_mapping(sources, "sources")
    for provider in REQUIRED_PROVIDERS:
        value = _require_field(mapping, provider, "sources")
        if not isinstance(value, str) or not value.strip():
            raise InvalidReferenceError(f"sources.{provider}: expected a non-empty URL string")


def _validate_profiles(profiles: object) -> None:
    mapping = _require_mapping(profiles, "profiles")
    for profile_name in REQUIRED_PROFILES:
        profile = _require_mapping(
            _require_field(mapping, profile_name, "profiles"),
            f"profiles.{profile_name}",
        )
        for provider in REQUIRED_PROVIDERS:
            provider_path = f"profiles.{profile_name}.{provider}"
            entry = _require_mapping(
                _require_field(profile, provider, f"profiles.{profile_name}"),
                provider_path,
            )
            model = _require_field(entry, "model", provider_path)
            if not isinstance(model, str) or not model.strip():
                raise InvalidReferenceError(f"{provider_path}.model: expected a non-empty string")


def _parse_last_verified(value: object) -> date:
    if not isinstance(value, str):
        raise InvalidReferenceError("last_verified: expected an ISO date string")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise InvalidReferenceError(f"last_verified: {exc}") from exc


def _parse_threshold(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise InvalidReferenceError("stale_after_days: expected a positive integer")
    return value


def check_staleness(reference_path: Path, today: date) -> StalenessReport:
    try:
        raw = reference_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InvalidReferenceError(f"{reference_path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InvalidReferenceError(f"{reference_path}: invalid JSON ({exc})") from exc

    document = _require_mapping(data, "<root>")
    last_verified = _parse_last_verified(_require_field(document, "last_verified", "<root>"))
    stale_after_days = _parse_threshold(_require_field(document, "stale_after_days", "<root>"))
    _validate_sources(_require_field(document, "sources", "<root>"))
    _validate_profiles(_require_field(document, "profiles", "<root>"))

    if last_verified > today:
        raise InvalidReferenceError(
            f"last_verified ({last_verified.isoformat()}) is in the future relative to today ({today.isoformat()})"
        )

    age_days = routing_age_days(last_verified, today)
    return StalenessReport(
        last_verified=last_verified,
        today=today,
        age_days=age_days,
        stale_after_days=stale_after_days,
        is_stale=age_days > stale_after_days,
    )


def _default_reference() -> Path:
    return Path(__file__).resolve().parents[3] / "model-routing.json"


def _parse_today(value: str | None) -> date:
    if value is None:
        # Timezone-aware to avoid naive-clock pitfalls; --today makes checks deterministic.
        return datetime.now(tz=UTC).date()
    return date.fromisoformat(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report model-routing reference staleness.")
    parser.add_argument(
        "--reference",
        type=Path,
        default=_default_reference(),
        help="Path to model-routing.json (defaults to the canonical root).",
    )
    parser.add_argument(
        "--today",
        default=None,
        help="Override today's date (YYYY-MM-DD) for deterministic checks.",
    )
    args = parser.parse_args(argv)

    try:
        today = _parse_today(args.today)
    except ValueError as exc:
        print(f"error: invalid --today value: {exc}", file=sys.stderr)
        return 2

    try:
        report = check_staleness(args.reference, today)
    except InvalidReferenceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    status = "STALE" if report.is_stale else "CURRENT"
    print(
        f"{status} last_verified={report.last_verified.isoformat()} "
        f"age_days={report.age_days} stale_after_days={report.stale_after_days}"
    )
    return 3 if report.is_stale else 0


if __name__ == "__main__":
    sys.exit(main())
