"""SkillCatalog — stdlib-only catalog updater for secret-agents/skills.

Usage:
  python catalog.py show    [--skills-root <dir>]
  python catalog.py update  [--skills-root <dir>]
  python catalog.py check   [--skills-root <dir>]
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from argparse import ArgumentParser
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1
CACHE_SCHEMA_VERSION = 1
CATALOG_FILENAME = "catalog.json"
TOC_FILENAME = "TOC.md"
CACHE_PATH = Path.home() / ".agents" / "cache" / "secret-agents-skill-catalog.json"

CATEGORIES: dict[str, str] = {
    "Agent Workflow": "a",
    "Code Quality": "c",
    "Jira": "j",
    "Maintenance": "m",
    "Preflight": "p",
    "Query & Discovery": "q",
    "Reporting": "r",
    "Skill Management": "s",
    "Testing": "t",
    "Unreal": "u",
}
CATEGORY_ORDER = list(CATEGORIES.keys())

NON_SKILL_NAMES = {"README.md", "README.html", CATALOG_FILENAME, TOC_FILENAME}

HEADER_RE = re.compile(
    r"\*\*Category:\*\* (?P<category>[A-Za-z &]+?) · "
    r"\*\*Short:\*\* (?P<shorthand>[a-z]+) · "
    r"\*\*Updated:\*\* (?P<updated>\d{4}-\d{2}-\d{2})"
    r"(?: · \*\*Aliases:\*\* (?P<aliases>[^\n]+))?"
)
GENERATED_MARKER_RE = re.compile(
    r"<!-- generated:(?P<canonical>[a-z][a-z0-9-]*):(?P<date>\d{4}-\d{2}-\d{2}) -->"
)
UPDATED_RE = re.compile(r"(\*\*Updated:\*\* )\d{4}-\d{2}-\d{2}")

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CatalogError(Exception):
    pass


class MissingFrontmatter(CatalogError):
    pass


class UnterminatedFrontmatter(CatalogError):
    pass


class MissingSkillHeader(CatalogError):
    pass


class MissingDisplayName(CatalogError):
    pass


class FrontmatterNameMismatch(CatalogError):
    pass


class UnknownCategory(CatalogError):
    pass


class InvalidShorthand(CatalogError):
    pass


class DuplicateName(CatalogError):
    pass


class HumanOwnedCollision(CatalogError):
    pass


class EmptyScan(CatalogError):
    pass


# ---------------------------------------------------------------------------
# Free-function helpers (pure text/path operations, no natural owner)
# ---------------------------------------------------------------------------


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        raise MissingFrontmatter("File does not begin with '---'")
    try:
        end = text.index("\n---\n", 4)
    except ValueError:
        raise UnterminatedFrontmatter("Frontmatter block never closed")
    block = text[4:end]
    pairs = (line.partition(": ") for line in block.splitlines() if ": " in line)
    return {k.strip(): v.strip().strip('"') for k, _, v in pairs}


def parse_skill_header(text: str) -> ParsedSkillHeader:
    m = HEADER_RE.search(text)
    if m is None:
        raise MissingSkillHeader("No canonical skill header found")
    aliases_raw = m.group("aliases") or ""
    aliases = tuple(a.strip() for a in aliases_raw.split(",") if a.strip())
    return ParsedSkillHeader(
        category=m.group("category").strip(),
        shorthand=m.group("shorthand"),
        updated=m.group("updated"),
        aliases=aliases,
    )


def extract_h1(text: str) -> str:
    h1 = next(
        (line[2:].strip() for line in text.splitlines()
         if line.startswith("# ") and not line.startswith("## ")),
        None,
    )
    if h1 is None:
        raise MissingDisplayName("No H1 heading found in SKILL.md")
    return h1


def compute_semantic_hash(text: str) -> str:
    """SHA-256 with Updated date replaced — unchanged by timestamp-only edits."""
    normalized = UPDATED_RE.sub(r"\1__date__", text)
    return hashlib.sha256(normalized.encode()).hexdigest()


def compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def is_generated_alias(skill_dir: Path) -> bool:
    """True when SKILL.md contains the machine-readable generated marker."""
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        return False
    return GENERATED_MARKER_RE.search(skill_file.read_text(encoding="utf-8")) is not None


def generate_alias_skill_md(alias: str, canonical: str, date: str, description: str) -> str:
    return (
        f"---\nname: {alias}\ndescription: Alias for {canonical}. {description}\n---\n\n"
        f"<!-- generated:{canonical}:{date} -->\n"
        f"# {alias}\n\n"
        f"Alias for `{canonical}`. Pass all arguments through unchanged.\n\n"
        f"## Behavior\n\n"
        f"Follow the `{canonical}` skill exactly. Treat all arguments passed to "
        f"`/{alias}` as arguments for `/{canonical}`.\n"
    )


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.write(fd, text.encode())
        os.close(fd)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ParsedSkillHeader:
    category: str
    shorthand: str
    updated: str
    aliases: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class CanonicalEntry:
    name: str
    display_name: str
    description: str
    category: str
    shorthand: str
    aliases: tuple[str, ...]
    updated: str
    semantic_hash: str
    content_hash: str

    @staticmethod
    def _validate_frontmatter(fm: dict[str, str], skill_dir: Path) -> tuple[str, str]:
        """Returns (name, description) after validating both fields."""
        name = fm.get("name", "")
        if not name:
            raise CatalogError(f"{skill_dir.name}/SKILL.md: missing 'name' in frontmatter")
        if name != skill_dir.name:
            raise FrontmatterNameMismatch(
                f"{skill_dir.name}/SKILL.md: frontmatter name '{name}' != directory"
            )
        description = fm.get("description", "")
        if not description:
            raise CatalogError(f"{skill_dir.name}/SKILL.md: missing 'description'")
        return name, description

    @classmethod
    def from_dir(cls, skill_dir: Path, today: str) -> CanonicalEntry:
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        name, description = cls._validate_frontmatter(parse_frontmatter(text), skill_dir)
        header = parse_skill_header(text)
        return cls(
            name=name,
            display_name=extract_h1(text),
            description=description,
            category=header.category,
            shorthand=header.shorthand,
            aliases=header.aliases,
            updated=header.updated,
            semantic_hash=compute_semantic_hash(text),
            content_hash=compute_content_hash(text),
        )

    def with_updated(self, date: str) -> CanonicalEntry:
        return dataclasses.replace(self, updated=date)


@dataclasses.dataclass
class StatEntry:
    size: int
    mtime_ns: int

    @classmethod
    def from_path(cls, skill_dir: Path) -> StatEntry:
        s = (skill_dir / "SKILL.md").stat()
        return cls(size=s.st_size, mtime_ns=s.st_mtime_ns)


@dataclasses.dataclass
class StatCache:
    schema_version: int
    agent_root: str
    catalog_hash: str
    entries: dict[str, StatEntry]  # "skill-name/SKILL.md" -> stat

    @classmethod
    def _from_dict(cls, data: dict, skills_root: Path) -> StatCache | None:
        if data.get("schema_version") != CACHE_SCHEMA_VERSION:
            return None
        if data.get("agent_root") != str(skills_root):
            return None
        entries = {k: StatEntry(**v) for k, v in data.get("entries", {}).items()}
        return cls(
            schema_version=data["schema_version"],
            agent_root=data["agent_root"],
            catalog_hash=data.get("catalog_hash", ""),
            entries=entries,
        )

    @classmethod
    def load(cls, path: Path, skills_root: Path) -> StatCache | None:
        if not path.is_file():
            return None
        try:
            return cls._from_dict(json.loads(path.read_text(encoding="utf-8")), skills_root)
        except Exception:
            return None

    def save(self, path: Path) -> None:
        data = {
            "schema_version": self.schema_version,
            "agent_root": self.agent_root,
            "catalog_hash": self.catalog_hash,
            "entries": {k: dataclasses.asdict(v) for k, v in self.entries.items()},
        }
        _atomic_write(path, json.dumps(data, indent=2))
