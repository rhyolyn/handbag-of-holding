"""Deterministic tests for the centralized model-routing reference and its age checker.

The reference under test is the tracked ``model-routing.json`` at the canonical root.
The checker module is loaded by file path so these tests do not depend on package
installation, matching how ``check_staleness.py`` is invoked as a standalone script.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent
REFERENCE_PATH = ROOT / "model-routing.json"
SCRIPT_PATH = ROOT / "skills" / "update-model-routing" / "scripts" / "check_staleness.py"

# The authoritative bootstrap content from the plan's Centralized Model Routing Reference.
EXPECTED_PROFILES = {
    "high-risk": {
        "codex": {"model": "gpt-5.6-sol", "reasoning": "high"},
        "claude": {"model": "claude-opus-5", "effort": "high"},
    },
    "balanced": {
        "codex": {"model": "gpt-5.6-terra", "reasoning": "high"},
        "claude": {"model": "claude-sonnet-5", "effort": "high"},
    },
    "routine": {
        "codex": {"model": "gpt-5.6-terra", "reasoning": "medium"},
        "claude": {"model": "claude-sonnet-5", "effort": "medium"},
    },
    "economy": {
        "codex": {"model": "gpt-5.6-luna", "reasoning": "low"},
        "claude": {"model": "claude-haiku-4-5-20251001", "effort": "standard"},
    },
}
EXPECTED_SOURCES = {
    "codex": "https://developers.openai.com/api/docs/models",
    "claude": "https://platform.claude.com/docs/en/models/overview",
}


def _load_checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_staleness", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclass type resolution can find the module namespace.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _valid_reference() -> dict[str, object]:
    return {
        "schema_version": 1,
        "last_verified": "2026-08-28",
        "stale_after_days": 31,
        "sources": dict(EXPECTED_SOURCES),
        "profiles": json.loads(json.dumps(EXPECTED_PROFILES)),
    }


def _write_reference(directory: Path, data: dict[str, object]) -> Path:
    path = directory / "model-routing.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_reference_matches_schema_and_profiles() -> None:
    data = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["stale_after_days"] == 31
    assert data["sources"] == EXPECTED_SOURCES
    assert data["profiles"] == EXPECTED_PROFILES


def test_age_31_days_is_current(capsys: pytest.CaptureFixture[str]) -> None:
    mod = _load_checker()
    report = mod.check_staleness(REFERENCE_PATH, date(2026, 9, 28))
    assert report.age_days == 31
    assert report.is_stale is False
    exit_code = mod.main(["--reference", str(REFERENCE_PATH), "--today", "2026-09-28"])
    out = capsys.readouterr().out
    assert out.startswith("CURRENT")
    assert "age_days=31" in out
    assert "stale_after_days=31" in out
    assert exit_code == 0


def test_age_32_days_is_stale(capsys: pytest.CaptureFixture[str]) -> None:
    mod = _load_checker()
    report = mod.check_staleness(REFERENCE_PATH, date(2026, 9, 29))
    assert report.age_days == 32
    assert report.is_stale is True
    exit_code = mod.main(["--reference", str(REFERENCE_PATH), "--today", "2026-09-29"])
    out = capsys.readouterr().out
    assert out.startswith("STALE")
    assert "age_days=32" in out
    assert exit_code == 3


def test_future_verification_date_is_invalid(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mod = _load_checker()
    data = _valid_reference()
    data["last_verified"] = "2026-09-01"
    ref = _write_reference(tmp_path, data)
    exit_code = mod.main(["--reference", str(ref), "--today", "2026-08-28"])
    err = capsys.readouterr().err
    assert exit_code == 2
    assert err.strip() != ""


def test_missing_provider_or_profile_field_is_invalid(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mod = _load_checker()
    data = _valid_reference()
    profiles = data["profiles"]
    assert isinstance(profiles, dict)
    del profiles["high-risk"]["claude"]
    ref = _write_reference(tmp_path, data)
    exit_code = mod.main(["--reference", str(ref), "--today", "2026-08-28"])
    err = capsys.readouterr().err
    assert exit_code == 2
    assert "high-risk" in err
    assert "claude" in err


def test_cli_today_override_is_deterministic(
    capsys: pytest.CaptureFixture[str],
) -> None:
    mod = _load_checker()
    exit_code = mod.main(["--reference", str(REFERENCE_PATH), "--today", "2026-09-29"])
    out = capsys.readouterr().out
    assert out.startswith("STALE")
    assert "last_verified=2026-08-28" in out
    assert "age_days=32" in out
    assert exit_code == 3
