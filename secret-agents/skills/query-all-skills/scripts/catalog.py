"""SkillCatalog — stdlib-only catalog updater for secret-agents/skills.

Usage:
  python catalog.py show    [--skills-root <dir>]
  python catalog.py update  [--skills-root <dir>]
  python catalog.py check   [--skills-root <dir>]
"""

from __future__ import annotations

import contextlib
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
from typing import IO, Any

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
GENERATED_MARKER_RE = re.compile(r"<!-- generated:(?P<canonical>[a-z][a-z0-9-]*):(?P<date>\d{4}-\d{2}-\d{2}) -->")
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
        raise UnterminatedFrontmatter("Frontmatter block never closed") from None
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
        (line[2:].strip() for line in text.splitlines() if line.startswith("# ") and not line.startswith("## ")),
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
        with contextlib.suppress(OSError):
            os.unlink(tmp)
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
            raise FrontmatterNameMismatch(f"{skill_dir.name}/SKILL.md: frontmatter name '{name}' != directory")
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
    def _from_dict(cls, data: dict[str, Any], skills_root: Path) -> StatCache | None:
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
    def _from_dict(cls, data: dict[str, Any]) -> Catalog | None:
        if data.get("schema_version") != SCHEMA_VERSION:
            return None
        raw_entries = data.get("entries", [])
        assert isinstance(raw_entries, list)
        entries = tuple(
            CanonicalEntry(**{k: tuple(v) if isinstance(v, list) else v for k, v in e.items()})  # type: ignore[arg-type]
            for e in raw_entries
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

    @staticmethod
    def _check_shorthand(entry: CanonicalEntry) -> None:
        prefix = CATEGORIES[entry.category]
        initials = "".join(w[0] for w in entry.name.split("-") if w)
        if not entry.shorthand.startswith(prefix):
            raise InvalidShorthand(f"{entry.name}: shorthand '{entry.shorthand}' must start with '{prefix}'")
        if not all(c in entry.shorthand for c in initials):
            raise InvalidShorthand(f"{entry.name}: shorthand '{entry.shorthand}' must contain initials '{initials}'")

    @staticmethod
    def _register_aliases(entry: CanonicalEntry, seen_aliases: set[str], seen_names: set[str]) -> None:
        for alias in entry.aliases:
            if alias in seen_aliases or alias in seen_names:
                raise DuplicateName(f"Duplicate alias: {alias}")
            if alias == entry.name:
                raise CatalogError(f"Alias '{alias}' equals canonical name")
            seen_aliases.add(alias)

    @staticmethod
    def _check_entry(
        entry: CanonicalEntry,
        seen_names: set[str],
        seen_shorthands: set[str],
        seen_aliases: set[str],
    ) -> None:
        if entry.name in seen_names:
            raise DuplicateName(f"Duplicate canonical name: {entry.name}")
        seen_names.add(entry.name)
        if entry.category not in CATEGORIES:
            raise UnknownCategory(f"{entry.name}: unknown category '{entry.category}'")
        Catalog._check_shorthand(entry)
        if entry.shorthand in seen_shorthands:
            raise DuplicateName(f"Duplicate shorthand: {entry.shorthand}")
        seen_shorthands.add(entry.shorthand)
        Catalog._register_aliases(entry, seen_aliases, seen_names)

    def validate(self) -> None:
        if not self.entries:
            raise EmptyScan("Catalog has zero canonical entries")
        seen_names: set[str] = set()
        seen_shorthands: set[str] = set()
        seen_aliases: set[str] = set()
        for entry in self.entries:
            self._check_entry(entry, seen_names, seen_shorthands, seen_aliases)


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

    def show(self, out: IO[str] | None = None) -> int:
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

    # -- Full refresh --------------------------------------------------------

    def _resolve_entry(self, skill_dir: Path, today: str, prev_by_name: dict[str, CanonicalEntry]) -> CanonicalEntry:
        entry = CanonicalEntry.from_dir(skill_dir, today)
        prev = prev_by_name.get(entry.name)
        return entry.with_updated(prev.updated) if prev and entry.semantic_hash == prev.semantic_hash else entry

    def _full_refresh(self) -> tuple[Catalog, str]:
        from datetime import date as _date

        today = _date.today().isoformat()

        prev_catalog = Catalog.load(self.skills_root / CATALOG_FILENAME)
        prev_by_name = {e.name: e for e in prev_catalog.entries} if prev_catalog else {}

        entries = [self._resolve_entry(d, today, prev_by_name) for d in self._scan_canonical_dirs()]
        new_catalog = Catalog.build(entries, today)
        new_catalog.validate()
        return new_catalog, new_catalog.render_toc()

    def _update_stat_cache(self, catalog_obj: Catalog) -> None:
        catalog_path = self.skills_root / CATALOG_FILENAME
        skill_dirs = self._scan_canonical_dirs()
        StatCache(
            schema_version=CACHE_SCHEMA_VERSION,
            agent_root=str(self.skills_root),
            catalog_hash=compute_content_hash(catalog_path.read_text(encoding="utf-8")),
            entries={f"{d.name}/SKILL.md": StatEntry.from_path(d) for d in skill_dirs},
        ).save(self.cache_path)

    def _publish(self, new_catalog: Catalog, toc_text: str) -> None:
        """Write aliases first, then catalog + TOC last (atomic sequence)."""
        self._write_generated_aliases(new_catalog, new_catalog.generated)
        self._retire_obsolete_aliases(new_catalog)
        new_catalog.save(self.skills_root / CATALOG_FILENAME)
        _atomic_write(self.skills_root / TOC_FILENAME, toc_text)

    def _show_slow(self, out: IO[str]) -> int:
        try:
            new_catalog, toc_text = self._full_refresh()
        except CatalogError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        self._publish(new_catalog, toc_text)
        self._update_stat_cache(new_catalog)
        out.write(toc_text)
        return 0

    # -- Public CLI commands -------------------------------------------------

    def update(self, out: IO[str] | None = None) -> int:
        if out is None:
            out = sys.stdout
        try:
            new_catalog, toc_text = self._full_refresh()
        except CatalogError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        self._publish(new_catalog, toc_text)
        self._update_stat_cache(new_catalog)
        out.write(toc_text)
        return 0

    def _catalog_issue(self, catalog_path: Path, new_catalog: Catalog) -> str | None:
        if not catalog_path.is_file():
            return "catalog.json is missing"
        actual_text = catalog_path.read_text(encoding="utf-8")
        expected_text = json.dumps(
            {
                "schema_version": new_catalog.schema_version,
                "generated": new_catalog.generated,
                "entries": [dataclasses.asdict(e) for e in new_catalog.entries],
                "generated_aliases": new_catalog.generated_aliases,
            },
            indent=2,
        )
        return "catalog.json is stale" if actual_text != expected_text else None

    def _toc_issue(self, toc_path: Path, expected_toc: str) -> str | None:
        if not toc_path.is_file():
            return "TOC.md is missing"
        return "TOC.md is stale" if toc_path.read_text(encoding="utf-8") != expected_toc else None

    def _alias_issue(self, alias: str) -> str | None:
        alias_dir = self.skills_root / alias
        if not (alias_dir / "SKILL.md").is_file():
            return f"Generated alias '{alias}' is missing"
        return None if is_generated_alias(alias_dir) else f"'{alias}' exists but lacks the generated marker"

    def check(self, out: IO[str] | None = None) -> int:
        if out is None:
            out = sys.stdout
        try:
            new_catalog, expected_toc = self._full_refresh()
        except CatalogError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        issues = [
            self._catalog_issue(self.skills_root / CATALOG_FILENAME, new_catalog),
            self._toc_issue(self.skills_root / TOC_FILENAME, expected_toc),
            *[self._alias_issue(a) for a in new_catalog.generated_aliases],
        ]
        real_issues = [i for i in issues if i is not None]
        if not real_issues:
            out.write("ok: catalog is current\n")
            return 0
        print("\n".join(f"drift: {i}" for i in real_issues), file=sys.stderr)
        return 1

    # -- Alias management ----------------------------------------------------

    def _write_generated_aliases(self, catalog_obj: Catalog, today: str) -> None:
        entry_by_name = {e.name: e for e in catalog_obj.entries}
        for alias, canonical in catalog_obj.generated_aliases.items():
            alias_dir = self.skills_root / alias
            if alias_dir.exists() and not is_generated_alias(alias_dir):
                raise HumanOwnedCollision(f"'{alias}' is a human-owned directory; cannot generate alias there")
            entry = entry_by_name.get(canonical)
            description = entry.description if entry else ""
            _atomic_write(
                alias_dir / "SKILL.md",
                generate_alias_skill_md(alias, canonical, today, description),
            )

    def _retire_obsolete_aliases(self, catalog_obj: Catalog) -> None:
        current = set(catalog_obj.generated_aliases.keys())
        for child in sorted(self.skills_root.iterdir()):
            if not child.is_dir() or child.name in current:
                continue
            if not is_generated_alias(child):
                continue
            unexpected = [f for f in child.iterdir() if f.name != "SKILL.md"]
            if unexpected:
                continue
            shutil.rmtree(child)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _default_skills_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def main() -> int:
    parser = ArgumentParser(description="SkillCatalog — validate and refresh secret-agents/skills")
    parser.add_argument(
        "command",
        choices=["show", "update", "check"],
        help="show: fast refresh + print TOC; update: force full refresh; check: detect drift",
    )
    parser.add_argument("--skills-root", type=Path, default=None)
    args = parser.parse_args()
    skills_root: Path = args.skills_root or _default_skills_root()
    sc = SkillCatalog(skills_root)
    if args.command == "show":
        return sc.show()
    if args.command == "update":
        return sc.update()
    if args.command == "check":
        return sc.check()
    return 1


if __name__ == "__main__":
    sys.exit(main())
