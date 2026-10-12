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


@dataclasses.dataclass(frozen=True)
class Catalog:
    schema_version: int
    generated: str
    entries: tuple[CanonicalEntry, ...]
    generated_aliases: dict[str, str]  # alias/shorthand -> canonical name

    @classmethod
    def build(cls, entries: list[CanonicalEntry], today: str) -> Catalog:
        """Assemble a Catalog from a list of (already date-resolved) entries."""
        aliases: dict[str, str] = {}
        for e in entries:
            aliases[e.shorthand] = e.name
            for a in e.aliases:
                aliases[a] = e.name
        ordered = tuple(
            sorted(
                entries,
                key=lambda e: (CATEGORY_ORDER.index(e.category), e.display_name),
            )
        )
        return cls(
            schema_version=SCHEMA_VERSION,
            generated=today,
            entries=ordered,
            generated_aliases=aliases,
        )

    @classmethod
    def _from_dict(cls, data: dict) -> Catalog | None:
        if data.get("schema_version") != SCHEMA_VERSION:
            return None
        entries = tuple(
            CanonicalEntry(**{k: tuple(v) if isinstance(v, list) else v for k, v in e.items()})
            for e in data.get("entries", [])
        )
        return cls(
            schema_version=data["schema_version"],
            generated=data.get("generated", ""),
            entries=entries,
            generated_aliases=data.get("generated_aliases", {}),
        )

    @classmethod
    def load(cls, path: Path) -> Catalog | None:
        if not path.is_file():
            return None
        try:
            return cls._from_dict(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            return None

    def save(self, path: Path) -> None:
        data = {
            "schema_version": self.schema_version,
            "generated": self.generated,
            "entries": [dataclasses.asdict(e) for e in self.entries],
            "generated_aliases": self.generated_aliases,
        }
        _atomic_write(path, json.dumps(data, indent=2))

    @staticmethod
    def _render_category_lines(cat: str, entries: list[CanonicalEntry]) -> list[str]:
        def entry_line(e: CanonicalEntry) -> str:
            alias_note = f" · Aliases: {', '.join(e.aliases)}" if e.aliases else ""
            return f"- {e.display_name} (`{e.shorthand}`) — {e.description}{alias_note}"
        return ["", f"## {cat} ({CATEGORIES[cat]})", ""] + [entry_line(e) for e in entries]

    def render_toc(self) -> str:
        by_cat: dict[str, list[CanonicalEntry]] = {}
        for entry in self.entries:
            by_cat.setdefault(entry.category, []).append(entry)
        lines = ["# Skills", "", f"Generated {self.generated}. Run `/<short>` or `/<canonical-name>`."]
        for cat in CATEGORY_ORDER:
            cat_entries = by_cat.get(cat)
            if cat_entries:
                lines.extend(self._render_category_lines(cat, cat_entries))
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# SkillCatalog — orchestrator
# ---------------------------------------------------------------------------


class SkillCatalog:
    def __init__(
        self,
        skills_root: Path,
        cache_path: Path = CACHE_PATH,
    ) -> None:
        self.skills_root = skills_root
        self.cache_path = cache_path

    # -- Directory scanning --------------------------------------------------

    def _is_canonical_dir(self, child: Path) -> bool:
        """True when child is a real skill dir (not a generated alias, not a non-dir)."""
        if not child.is_dir() or child.name in NON_SKILL_NAMES:
            return False
        if is_generated_alias(child):
            return False
        if not (child / "SKILL.md").is_file():
            raise CatalogError(f"Non-generated directory '{child.name}' has no SKILL.md")
        return True

    def _scan_canonical_dirs(self) -> list[Path]:
        return [child for child in sorted(self.skills_root.iterdir()) if self._is_canonical_dir(child)]

    def _fast_canonical_stats(self, generated_alias_names: set[str]) -> dict[str, StatEntry] | None:
        """Enumerate canonical dirs by stat only — no SKILL.md reads.

        Returns None when an unexpected dir (no SKILL.md) is found, forcing slow path.
        """
        result: dict[str, StatEntry] = {}
        for child in sorted(self.skills_root.iterdir()):
            if not child.is_dir() or child.name in NON_SKILL_NAMES:
                continue
            if child.name in generated_alias_names:
                continue
            skill_file = child / "SKILL.md"
            if not skill_file.is_file():
                return None
            result[f"{child.name}/SKILL.md"] = StatEntry.from_path(child)
        return result

    # -- CLI commands --------------------------------------------------------

    def show(self, out=None) -> int:
        """Fast refresh + print TOC. Reads no SKILL.md bodies on a warm cache."""
        if out is None:
            out = sys.stdout
        toc_path = self.skills_root / TOC_FILENAME
        catalog_path = self.skills_root / CATALOG_FILENAME
        catalog_text = catalog_path.read_text(encoding="utf-8") if catalog_path.is_file() else None
        stat_cache = StatCache.load(self.cache_path, self.skills_root)
        if not (stat_cache and catalog_text):
            return self._show_slow(out)
        if stat_cache.catalog_hash != compute_content_hash(catalog_text):
            return self._show_slow(out)
        catalog_data = json.loads(catalog_text)
        generated_alias_names = set(catalog_data.get("generated_aliases", {}).keys())
        current = self._fast_canonical_stats(generated_alias_names)
        if current is None or current != stat_cache.entries or not toc_path.is_file():
            return self._show_slow(out)
        out.write(toc_path.read_text(encoding="utf-8"))
        return 0

    def _show_slow(self, out) -> int:  # stub — implemented in Task 5
        return 1
