"""Behavioral tests for the skills README renderer and drift guard."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
README_PATH = ROOT / "skills" / "README.md"
SCRIPT_PATH = ROOT / "skills" / "update-skills-readme" / "scripts" / "render_html.py"


def _load_renderer() -> ModuleType:
    spec = importlib.util.spec_from_file_location("render_html", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_verify_accepts_the_documented_skill_catalog() -> None:
    renderer = _load_renderer()
    skill_names = renderer.skill_directories(ROOT / "skills")

    assert renderer.verify(README_PATH.read_text(encoding="utf-8"), skill_names) == []


def test_verify_reports_missing_catalog_entries_and_dead_anchors() -> None:
    renderer = _load_renderer()
    markdown = "# Skills\n\n- [alpha](#alpha)\n- [broken](#missing)\n\n### alpha\n"

    assert renderer.verify(markdown, ["alpha", "bravo"]) == [
        "missing section heading: ### bravo",
        "missing TOC/inventory link: #bravo",
        "dead anchor: #missing",
    ]
