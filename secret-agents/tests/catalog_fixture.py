"""Catalog fixtures that mirror the generated install projection."""

from __future__ import annotations

import json
from pathlib import Path


def write_catalog(skills_root: Path, *names: str) -> None:
    """Create collection sources and catalog-owned generated adapters."""
    entries = []
    projection = {}
    for name in names:
        source = skills_root / "work-tracking" / name
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")
        adapter = skills_root / "_generated" / name
        adapter.mkdir(parents=True)
        (adapter / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")
        entries.append(
            {
                "name": name,
                "description": f"Use {name}.",
                "collection": "work-tracking",
                "source_path": f"work-tracking/{name}",
            }
        )
        projection[name] = f"_generated/{name}"
    (skills_root / "collections.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_layout": "collections",
                "collections": [{"name": "work-tracking", "display_name": "Work Tracking", "description": "Tests."}],
            }
        ),
        encoding="utf-8",
    )
    (skills_root / "catalog.json").write_text(
        json.dumps(
            {"schema_version": 2, "generated": "2026-10-15", "entries": entries, "generated_projection": projection}
        ),
        encoding="utf-8",
    )
