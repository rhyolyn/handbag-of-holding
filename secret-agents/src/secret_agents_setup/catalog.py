"""Load installable skill descriptors from canonical catalog sources."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

from .catalog_errors import InvalidSkillCatalog, SkillsDirectoryNotFound
from .catalog_errors import SkillCatalogError as SkillCatalogError
from .models import SkillDescriptor

CATALOG_SCHEMA_VERSION = 2
CATALOG_FILENAME = "catalog.json"
NAME_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")


def load_skill_catalog(skills_root: Path, vault_root: Path | None = None) -> tuple[SkillDescriptor, ...]:
    """Return canonical descriptors whose directories are canonical sources."""
    if not skills_root.is_dir():
        raise SkillsDirectoryNotFound(skills_root)

    catalog_path = skills_root / CATALOG_FILENAME
    raw = _load_catalog_json(catalog_path, skills_root, vault_root)
    entries = _catalog_entries(raw, catalog_path, skills_root, vault_root)
    return _descriptors(entries, catalog_path, skills_root, vault_root)


def resolve_vault_root(
    vault_root: Path | None = None, *, environment: Mapping[str, str] | None = None, home: Path | None = None
) -> Path:
    """Select an explicit vault, then the configured vault, then the user default."""
    if vault_root is not None:
        return vault_root.expanduser().resolve()
    environment = os.environ if environment is None else environment
    configured = environment.get("SECRET_AGENTS_VAULT_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    home = Path.home() if home is None else home
    return (home / "obsidian").resolve()


def _load_catalog_json(catalog_path: Path, skills_root: Path, vault_root: Path | None) -> Mapping[str, Any]:
    if not catalog_path.is_file():
        _invalid(catalog_path, skills_root, vault_root, "missing generated catalog.json")
    try:
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _invalid(catalog_path, skills_root, vault_root, f"invalid catalog JSON ({exc})")
    if not isinstance(raw, dict):
        _invalid(catalog_path, skills_root, vault_root, "catalog must be a JSON object")
    if raw.get("schema_version") != CATALOG_SCHEMA_VERSION:
        _invalid(catalog_path, skills_root, vault_root, "catalog schema_version must be 2")
    return raw


def _catalog_entries(
    raw: Mapping[str, Any], catalog_path: Path, skills_root: Path, vault_root: Path | None
) -> tuple[Mapping[str, Any], ...]:
    entries = raw.get("entries")
    if not isinstance(entries, list) or not entries:
        _invalid(catalog_path, skills_root, vault_root, "catalog entries must be a non-empty array")
    result: list[Mapping[str, Any]] = []
    names: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            _invalid(catalog_path, skills_root, vault_root, f"entries[{index}] must be an object")
        name, description, source_path = (entry.get(field) for field in ("name", "description", "source_path"))
        if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
            _invalid(
                catalog_path,
                skills_root,
                vault_root,
                f"entries[{index}].name must be canonical lowercase hyphenated text",
            )
        if name in names:
            _invalid(catalog_path, skills_root, vault_root, f"duplicate canonical name {name!r}")
        if not isinstance(description, str) or not description:
            _invalid(catalog_path, skills_root, vault_root, f"entries[{index}].description must be non-empty text")
        if not isinstance(source_path, str) or not _is_canonical_source_path(source_path):
            _invalid(
                catalog_path,
                skills_root,
                vault_root,
                f"entries[{index}].source_path must be canonical collection/name text",
            )
        if PurePosixPath(source_path).name != name:
            _invalid(
                catalog_path,
                skills_root,
                vault_root,
                f"entries[{index}].source_path must end with canonical name {name!r}",
            )
        names.add(name)
        result.append(entry)
    return tuple(result)


def _descriptors(
    entries: tuple[Mapping[str, Any], ...],
    catalog_path: Path,
    skills_root: Path,
    vault_root: Path | None,
) -> tuple[SkillDescriptor, ...]:
    descriptors: list[SkillDescriptor] = []
    for entry in entries:
        name = entry["name"]
        description = entry["description"]
        assert isinstance(name, str) and isinstance(description, str)
        source_path = entry["source_path"]
        assert isinstance(source_path, str)
        directory = skills_root.joinpath(*PurePosixPath(source_path).parts)
        if not (directory / "SKILL.md").is_file():
            _invalid(catalog_path, skills_root, vault_root, f"{source_path}/SKILL.md is missing")
        descriptors.append(SkillDescriptor(name, description, directory))
    return tuple(sorted(descriptors, key=lambda descriptor: descriptor.name))


def _is_canonical_source_path(value: str) -> bool:
    path = PurePosixPath(value)
    return (
        bool(value)
        and "\\" not in value
        and len(path.parts) == 2
        and all(NAME_PATTERN.fullmatch(part) for part in path.parts)
    )


def _invalid(catalog_path: Path, skills_root: Path, vault_root: Path | None, detail: str) -> NoReturn:
    vault = resolve_vault_root(vault_root)
    remediation = f"run catalog.py update --vault-root {vault}"
    raise InvalidSkillCatalog(catalog_path, detail, remediation)
