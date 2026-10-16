"""Standalone tools must use the user's canonical vault, independent of cwd."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("script", "arguments", "expected_relative"),
    [
        ("skill-authoring/query-all-skills/scripts/catalog.py", ["check"], "skills"),
        ("skill-authoring/update-skills-readme/scripts/render_html.py", [], "skills/README.md"),
        ("maintenance/update-model-routing/scripts/check_staleness.py", [], "model-routing.json"),
    ],
)
@pytest.mark.parametrize("override", [False, True])
def test_standalone_tools_refuse_missing_home_source(
    tmp_path: Path, script: str, arguments: list[str], expected_relative: str, override: bool
) -> None:
    home = tmp_path / "User With Spaces"
    home.mkdir()
    environment = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
    environment.pop("SECRET_AGENTS_ROOT", None)
    source = home / "obsidian" / "handbag-of-holding" / "secret-agents"
    if override:
        vault = home / "explicit vault"
        source = vault / "handbag-of-holding" / "secret-agents"
        environment["SECRET_AGENTS_ROOT"] = str(source)
        environment["SECRET_AGENTS_VAULT_ROOT"] = str(vault)
    result = subprocess.run(
        [sys.executable, str(ROOT / "skills" / script), *arguments],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert str(source / expected_relative) in result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert not source.exists()


@pytest.mark.parametrize("selection", ["default", "environment", "explicit"])
def test_catalog_tool_uses_the_selected_vault_source(tmp_path: Path, selection: str) -> None:
    home = tmp_path / "User With Spaces"
    home.mkdir()
    environment = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
    environment.pop("SECRET_AGENTS_ROOT", None)
    source = home / "obsidian" / "handbag-of-holding" / "secret-agents"
    if selection != "default":
        vault = home / "selected vault"
        source = vault / "handbag-of-holding" / "secret-agents"
        environment["SECRET_AGENTS_VAULT_ROOT"] = str(vault)
        environment["SECRET_AGENTS_ROOT"] = str(source if selection == "environment" else home / "wrong source")
    skills = source / "skills"
    skill = skills / "work-tracking" / "run-unit-tests"
    skill.mkdir(parents=True)
    shutil.copyfile(ROOT / "skills/code-quality/run-unit-tests/SKILL.md", skill / "SKILL.md")
    (skills / "collections.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_layout": "collections",
                "collections": [
                    {"name": "work-tracking", "display_name": "Work Tracking", "description": "Test fixture."}
                ],
            }
        ),
        encoding="utf-8",
    )
    catalog_args = ["--vault-root", "~/selected vault"] if selection == "explicit" else []
    commands = [
        ("skill-authoring/query-all-skills/scripts/catalog.py", ["update", *catalog_args]),
        ("skill-authoring/query-all-skills/scripts/catalog.py", ["check", *catalog_args]),
    ]
    for script, arguments in commands:
        result = subprocess.run(
            [sys.executable, str(ROOT / "skills" / script), *arguments],
            cwd=tmp_path,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    assert (skills / "catalog.json").is_file()
    assert (skills / "_generated/run-unit-tests/SKILL.md").is_file()
    assert not (home / "wrong source").exists()
