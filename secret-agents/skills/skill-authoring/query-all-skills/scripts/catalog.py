"""Validate and publish the secret-agents skill catalog and install projection."""

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
from datetime import date
from pathlib import Path
from typing import IO

SCHEMA_VERSION = 2
CACHE_SCHEMA_VERSION = 2
MANIFEST_SCHEMA_VERSION = 1
CATALOG_FILENAME = "catalog.json"
TOC_FILENAME = "TOC.md"
MANIFEST_FILENAME = "collections.json"
GENERATED_DIRECTORY = "_generated"
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
CATEGORY_ORDER = tuple(CATEGORIES)
NAME_RE = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
HEADER_RE = re.compile(
    r"\*\*Category:\*\* (?P<category>[A-Za-z &]+?) · \*\*Updated:\*\* (?P<updated>\d{4}-\d{2}-\d{2})"
)
UPDATED_RE = re.compile(r"(\*\*Updated:\*\* )\d{4}-\d{2}-\d{2}")
PROJECTION_MARKER_RE = re.compile(
    r"<!-- generated-projection:(?P<canonical>[a-z][a-z0-9-]*):(?P<date>\d{4}-\d{2}-\d{2}) -->"
)
LEGACY_GENERATED_MARKER_RE = re.compile(
    r"<!-- generated:(?P<canonical>[a-z][a-z0-9-]*):(?P<date>\d{4}-\d{2}-\d{2}) -->"
)


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


class DuplicateName(CatalogError):
    pass


class HumanOwnedCollision(CatalogError):
    pass


class EmptyScan(CatalogError):
    pass


class InvalidManifest(CatalogError):
    pass


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        raise MissingFrontmatter("File does not begin with '---'")
    try:
        end = text.index("\n---\n", 4)
    except ValueError:
        raise UnterminatedFrontmatter("Frontmatter block never closed") from None
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        key, separator, value = line.partition(": ")
        if not separator:
            continue
        value = value.strip()
        if value.startswith('"'):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise CatalogError(f"Invalid quoted frontmatter value for {key}: {exc}") from exc
        fields[key.strip()] = value
    return fields


@dataclasses.dataclass(frozen=True)
class ParsedSkillHeader:
    category: str
    updated: str


def parse_skill_header(text: str) -> ParsedSkillHeader:
    lines = text.splitlines()
    h1_index = next((index for index, line in enumerate(lines) if line.startswith("# ")), None)
    header = next((line for line in lines[h1_index + 1 :] if line.strip()), "") if h1_index is not None else ""
    match = HEADER_RE.fullmatch(header)
    if match is None:
        raise MissingSkillHeader("Expected a canonical Category / Updated header immediately after the H1")
    try:
        date.fromisoformat(match.group("updated"))
    except ValueError:
        raise CatalogError(f"Invalid Updated date: {match.group('updated')}") from None
    return ParsedSkillHeader(match.group("category").strip(), match.group("updated"))


def extract_h1(text: str) -> str:
    heading = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), None)
    if heading is None:
        raise MissingDisplayName("No H1 heading found in SKILL.md")
    return heading


def compute_semantic_hash(text: str) -> str:
    return hashlib.sha256(UPDATED_RE.sub(r"\1__date__", text).encode()).hexdigest()


def compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def compute_instruction_body_hash(text: str) -> str:
    lines = text.splitlines(keepends=True)
    h1_index = next((index for index, line in enumerate(lines) if line.startswith("# ")), None)
    if h1_index is None:
        raise MissingDisplayName("No H1 heading found in SKILL.md")
    header_index = next((index for index in range(h1_index + 1, len(lines)) if lines[index].strip()), None)
    if header_index is None:
        raise MissingSkillHeader("Expected a canonical skill header immediately after the H1")
    return hashlib.sha256("".join(lines[header_index + 1 :]).lstrip("\r\n").encode()).hexdigest()


def _atomic_write(path: Path, text: str) -> None:
    _atomic_write_bytes(path, text.encode())


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.write(descriptor, content)
        os.close(descriptor)
        os.replace(temporary, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise


@dataclasses.dataclass(frozen=True)
class CollectionSpec:
    name: str
    display_name: str
    description: str


@dataclasses.dataclass(frozen=True)
class CanonicalSource:
    collection: str
    directory: Path
    source_path: str


@dataclasses.dataclass(frozen=True)
class CanonicalEntry:
    name: str
    collection: str
    source_path: str
    display_name: str
    description: str
    category: str
    updated: str
    semantic_hash: str
    content_hash: str

    @classmethod
    def from_source(cls, source: CanonicalSource) -> CanonicalEntry:
        skill_file = source.directory / "SKILL.md"
        text = skill_file.read_text(encoding="utf-8")
        frontmatter = parse_frontmatter(text)
        name = frontmatter.get("name", "")
        if not name:
            raise CatalogError(f"{skill_file}: missing 'name' in frontmatter")
        if name != source.directory.name:
            raise FrontmatterNameMismatch(f"{skill_file}: frontmatter name '{name}' != directory")
        description = frontmatter.get("description", "")
        if not description:
            raise CatalogError(f"{skill_file}: missing 'description'")
        header = parse_skill_header(text)
        return cls(
            name,
            source.collection,
            source.source_path,
            extract_h1(text),
            description,
            header.category,
            header.updated,
            compute_semantic_hash(text),
            compute_content_hash(text),
        )


@dataclasses.dataclass(frozen=True)
class StatEntry:
    size: int
    mtime_ns: int

    @classmethod
    def from_file(cls, path: Path) -> StatEntry:
        stat = path.stat()
        return cls(stat.st_size, stat.st_mtime_ns)


@dataclasses.dataclass(frozen=True)
class StatCache:
    schema_version: int
    skills_root: str
    catalog_hash: str
    entries: dict[str, StatEntry]

    @classmethod
    def load(cls, path: Path, skills_root: Path) -> StatCache | None:
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if raw.get("schema_version") != CACHE_SCHEMA_VERSION or raw.get("skills_root") != str(skills_root):
                return None
            return cls(
                raw["schema_version"],
                raw["skills_root"],
                raw["catalog_hash"],
                {key: StatEntry(**value) for key, value in raw["entries"].items()},
            )
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def save(self, path: Path) -> None:
        _atomic_write(
            path,
            json.dumps(
                {
                    "schema_version": self.schema_version,
                    "skills_root": self.skills_root,
                    "catalog_hash": self.catalog_hash,
                    "entries": {name: dataclasses.asdict(stat) for name, stat in self.entries.items()},
                },
                indent=2,
            ),
        )


@dataclasses.dataclass(frozen=True)
class Catalog:
    schema_version: int
    generated: str
    entries: tuple[CanonicalEntry, ...]
    generated_projection: dict[str, str]

    @classmethod
    def build(cls, entries: list[CanonicalEntry], today: str, collections: tuple[CollectionSpec, ...]) -> Catalog:
        collection_order = {collection.name: index for index, collection in enumerate(collections)}
        ordered = tuple(
            sorted(
                entries,
                key=lambda entry: (
                    collection_order.get(entry.collection, len(collection_order)),
                    CATEGORY_ORDER.index(entry.category) if entry.category in CATEGORIES else len(CATEGORY_ORDER),
                    entry.display_name,
                ),
            )
        )
        return cls(
            SCHEMA_VERSION, today, ordered, {entry.name: f"{GENERATED_DIRECTORY}/{entry.name}" for entry in ordered}
        )

    @classmethod
    def load(cls, path: Path) -> Catalog | None:
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if raw.get("schema_version") != SCHEMA_VERSION:
                return None
            projection = raw["generated_projection"]
            if not isinstance(projection, dict):
                return None
            return cls(
                raw["schema_version"],
                raw["generated"],
                tuple(CanonicalEntry(**entry) for entry in raw["entries"]),
                projection,
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def as_json(self) -> str:
        return json.dumps(
            {
                "schema_version": self.schema_version,
                "generated": self.generated,
                "entries": [dataclasses.asdict(entry) for entry in self.entries],
                "generated_projection": self.generated_projection,
            },
            indent=2,
        )

    def validate(self) -> None:
        if not self.entries:
            raise EmptyScan("Catalog has zero canonical entries")
        names: dict[str, str] = {}
        for entry in self.entries:
            if not NAME_RE.fullmatch(entry.name):
                raise CatalogError(f"{entry.source_path}: invalid canonical name '{entry.name}'")
            if entry.name in names:
                raise DuplicateName(
                    f"{entry.source_path}: duplicate canonical name '{entry.name}' also declared at {names[entry.name]}"
                )
            names[entry.name] = entry.source_path
            if entry.category not in CATEGORIES:
                raise UnknownCategory(f"{entry.source_path}: unknown category '{entry.category}'")
            if self.generated_projection.get(entry.name) != f"{GENERATED_DIRECTORY}/{entry.name}":
                raise CatalogError(f"{entry.source_path}: invalid generated projection mapping")

    def render_toc(self, collections: tuple[CollectionSpec, ...]) -> str:
        lines = ["# Skills", "", f"Generated {self.generated}. Run `/<canonical-name>`."]
        for collection in collections:
            collection_entries = [entry for entry in self.entries if entry.collection == collection.name]
            if not collection_entries:
                continue
            lines.extend(["", f"## {collection.display_name}", "", collection.description])
            for category in CATEGORY_ORDER:
                category_entries = [entry for entry in collection_entries if entry.category == category]
                if category_entries:
                    lines.extend(["", f"### {category} ({CATEGORIES[category]})", ""])
                    lines.extend(
                        f"- /{entry.name}: {entry.description.replace('—', '-')}" for entry in category_entries
                    )
        return "\n".join(lines) + "\n"


class SkillCatalog:
    def __init__(self, skills_root: Path, cache_path: Path = CACHE_PATH) -> None:
        self.skills_root, self.cache_path = skills_root, cache_path

    def _load_manifest(self) -> tuple[CollectionSpec, ...]:
        manifest_path = self.skills_root / MANIFEST_FILENAME
        if not manifest_path.is_file():
            raise InvalidManifest(
                f"{manifest_path}: missing manifest; run catalog.py check --skills-root {self.skills_root}"
            )
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise InvalidManifest(f"{manifest_path}: invalid JSON ({exc.msg})") from None
        if not isinstance(raw, dict) or raw.get("schema_version") != MANIFEST_SCHEMA_VERSION:
            raise InvalidManifest(f"{manifest_path}: expected schema_version {MANIFEST_SCHEMA_VERSION}")
        if raw.get("source_layout") != "collections":
            raise InvalidManifest(f"{manifest_path}: source_layout must be 'collections'")
        records = raw.get("collections")
        if not isinstance(records, list):
            raise InvalidManifest(f"{manifest_path}: collections must be a list")
        collections: list[CollectionSpec] = []
        names: set[str] = set()
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise InvalidManifest(f"{manifest_path}: collections[{index}] must be an object")
            values = tuple(record.get(key) for key in ("name", "display_name", "description"))
            if not all(isinstance(value, str) and value for value in values):
                raise InvalidManifest(
                    f"{manifest_path}: collections[{index}] requires name, display_name, and description"
                )
            name, display_name, description = values
            assert isinstance(name, str) and isinstance(display_name, str) and isinstance(description, str)
            if not NAME_RE.fullmatch(name) or name == GENERATED_DIRECTORY or name in names:
                raise InvalidManifest(f"{manifest_path}: invalid, duplicate, or reserved collection name '{name}'")
            names.add(name)
            collections.append(CollectionSpec(name, display_name, description))
        if not collections:
            raise InvalidManifest(f"{manifest_path}: collections layout requires at least one collection")
        return tuple(collections)

    def _structural_error(self, path: Path, detail: str) -> CatalogError:
        return CatalogError(
            f"{path}: {detail}; fix the source and run catalog.py check --skills-root {self.skills_root}"
        )

    @staticmethod
    def _legacy_generated_target(directory: Path) -> str | None:
        skill_file = directory / "SKILL.md"
        if not skill_file.is_file():
            return None
        match = LEGACY_GENERATED_MARKER_RE.search(skill_file.read_text(encoding="utf-8"))
        return match.group("canonical") if match else None

    def _legacy_generated_directories(self, collections: tuple[CollectionSpec, ...]) -> tuple[tuple[Path, str], ...]:
        declared = {collection.name for collection in collections}
        legacy: list[tuple[Path, str]] = []
        for child in self.skills_root.iterdir():
            if child.is_file() and child.name == "SKILL.md":
                raise self._structural_error(child, "SKILL.md must be at collection/canonical depth")
            if not child.is_dir() or child.name == GENERATED_DIRECTORY or child.name in declared:
                continue
            canonical = self._legacy_generated_target(child)
            if canonical is None:
                raise self._structural_error(child, "undeclared collection")
            legacy.append((child, canonical))
        return tuple(legacy)

    def _scan_collection_sources(self, collections: tuple[CollectionSpec, ...]) -> tuple[CanonicalSource, ...]:
        self._legacy_generated_directories(collections)
        sources: list[CanonicalSource] = []
        for collection in collections:
            collection_dir = self.skills_root / collection.name
            if not collection_dir.is_dir():
                raise self._structural_error(collection_dir, "declared collection directory is missing")
            for skill_file in collection_dir.rglob("SKILL.md"):
                if len(skill_file.relative_to(collection_dir).parts) != 2:
                    raise self._structural_error(skill_file, "SKILL.md must be at collection/canonical depth")
            for child in sorted(collection_dir.iterdir()):
                if child.name == "README.md":
                    continue
                if not child.is_dir():
                    raise self._structural_error(
                        child, "collection entries must be canonical skill directories or README.md"
                    )
                if not (child / "SKILL.md").is_file():
                    raise self._structural_error(child, "canonical skill directory is missing SKILL.md")
                sources.append(CanonicalSource(collection.name, child, f"{collection.name}/{child.name}"))
        return tuple(sources)

    def _scan_canonical_sources(self) -> tuple[CanonicalSource, ...]:
        return self._scan_collection_sources(self._load_manifest())

    def _full_refresh(self) -> tuple[Catalog, str]:
        collections = self._load_manifest()
        sources = self._scan_collection_sources(collections)
        previous_catalog = Catalog.load(self.skills_root / CATALOG_FILENAME)
        previous = {entry.name: entry for entry in previous_catalog.entries} if previous_catalog else {}
        today = date.today().isoformat()
        entries: list[CanonicalEntry] = []
        for source in sources:
            entry = CanonicalEntry.from_source(source)
            updated = (
                previous[entry.name].updated
                if entry.name in previous and entry.semantic_hash == previous[entry.name].semantic_hash
                else today
            )
            text = (source.directory / "SKILL.md").read_text(encoding="utf-8")
            entries.append(
                dataclasses.replace(
                    entry, updated=updated, content_hash=compute_content_hash(UPDATED_RE.sub(r"\g<1>" + updated, text))
                )
            )
        catalog = Catalog.build(entries, today, collections)
        catalog.validate()
        if (
            previous_catalog
            and catalog.entries == previous_catalog.entries
            and catalog.generated_projection == previous_catalog.generated_projection
        ):
            catalog = dataclasses.replace(catalog, generated=previous_catalog.generated)
        return catalog, catalog.render_toc(collections)

    @staticmethod
    def _adapter_text(entry: CanonicalEntry, generated: str) -> str:
        return (
            f"---\nname: {entry.name}\ndescription: {json.dumps(entry.description, ensure_ascii=False)}\n---\n\n"
            f"<!-- generated-projection:{entry.name}:{generated} -->\n# {entry.name}\n\n"
            "Resolve this adapter's actual filesystem path; then, from its directory, read and follow "
            f"the canonical source: `../../{entry.source_path}/SKILL.md`.\n"
        )

    def _preflight_projection(self, catalog: Catalog) -> tuple[Path, ...]:
        generated_root = self.skills_root / GENERATED_DIRECTORY
        if generated_root.exists() and not generated_root.is_dir():
            raise HumanOwnedCollision(f"{generated_root}: generated projection root is not a directory")
        expected = set(catalog.generated_projection)
        if generated_root.is_dir():
            for child in generated_root.iterdir():
                skill_file = child / "SKILL.md"
                if (
                    not child.is_dir()
                    or not skill_file.is_file()
                    or PROJECTION_MARKER_RE.search(skill_file.read_text(encoding="utf-8")) is None
                ):
                    raise HumanOwnedCollision(f"{child}: human-owned generated projection collision")
                if any(path.name != "SKILL.md" for path in child.iterdir()):
                    raise HumanOwnedCollision(f"{child}: generated projection contains human-owned files")
        for entry in catalog.entries:
            if not (self.skills_root / entry.source_path / "SKILL.md").is_file():
                raise self._structural_error(
                    self.skills_root / entry.source_path / "SKILL.md", "canonical source disappeared before publication"
                )
        legacy: list[Path] = []
        expected = set(catalog.generated_projection)
        for directory, canonical in self._legacy_generated_directories(self._load_manifest()):
            if canonical not in expected:
                raise self._structural_error(
                    directory, f"legacy adapter points to missing canonical skill {canonical!r}"
                )
            if any(path.name != "SKILL.md" for path in directory.iterdir()):
                raise HumanOwnedCollision(f"{directory}: legacy generated adapter contains human-owned files")
            legacy.append(directory)
        return tuple(legacy)

    def _publish(self, catalog: Catalog, toc_text: str) -> None:
        legacy_directories = self._preflight_projection(catalog)
        generated_root = self.skills_root / GENERATED_DIRECTORY
        backup_root = self.skills_root / f".{GENERATED_DIRECTORY}-backup"
        if backup_root.exists():
            raise CatalogError(f"{backup_root}: stale publication backup; remove it and rerun catalog.py check")
        generated_existed = generated_root.exists()
        stage_parent = Path(tempfile.mkdtemp(dir=self.skills_root, prefix=".catalog-stage-"))
        stage_root = stage_parent / GENERATED_DIRECTORY
        source_originals: dict[Path, bytes] = {}
        derived_originals = {
            self.skills_root / CATALOG_FILENAME: self._read_optional_bytes(self.skills_root / CATALOG_FILENAME),
            self.skills_root / TOC_FILENAME: self._read_optional_bytes(self.skills_root / TOC_FILENAME),
        }
        projection_replaced = False
        try:
            for entry in catalog.entries:
                projection = stage_root / entry.name / "SKILL.md"
                projection.parent.mkdir(parents=True)
                projection.write_text(self._adapter_text(entry, catalog.generated), encoding="utf-8")
            for entry in catalog.entries:
                source_file = self.skills_root / entry.source_path / "SKILL.md"
                text = source_file.read_text(encoding="utf-8")
                dated = UPDATED_RE.sub(r"\g<1>" + entry.updated, text)
                if text != dated:
                    source_originals[source_file] = source_file.read_bytes()
                    _atomic_write(source_file, dated)
            if generated_root.exists():
                os.replace(generated_root, backup_root)
                try:
                    os.replace(stage_root, generated_root)
                    projection_replaced = True
                except Exception:
                    os.replace(backup_root, generated_root)
                    raise
            else:
                os.replace(stage_root, generated_root)
                projection_replaced = True
            _atomic_write(self.skills_root / CATALOG_FILENAME, catalog.as_json())
            _atomic_write(self.skills_root / TOC_FILENAME, toc_text)
        except OSError as exc:
            self._restore_publication(
                generated_root,
                backup_root,
                generated_existed,
                projection_replaced,
                source_originals,
                derived_originals,
            )
            raise CatalogError(f"publication failed: {exc}") from exc
        finally:
            if stage_parent.exists():
                shutil.rmtree(stage_parent)
        try:
            for directory in legacy_directories:
                shutil.rmtree(directory)
            if backup_root.exists():
                shutil.rmtree(backup_root)
        except OSError as exc:
            raise CatalogError(f"publication completed but cleanup failed: {exc}") from exc

    @staticmethod
    def _read_optional_bytes(path: Path) -> bytes | None:
        return path.read_bytes() if path.is_file() else None

    @staticmethod
    def _restore_optional_bytes(path: Path, original: bytes | None) -> None:
        current = SkillCatalog._read_optional_bytes(path)
        if current == original:
            return
        if original is None:
            path.unlink(missing_ok=True)
        else:
            _atomic_write_bytes(path, original)

    def _restore_publication(
        self,
        generated_root: Path,
        backup_root: Path,
        generated_existed: bool,
        projection_replaced: bool,
        source_originals: dict[Path, bytes],
        derived_originals: dict[Path, bytes | None],
    ) -> None:
        for source_path, source_original in source_originals.items():
            self._restore_optional_bytes(source_path, source_original)
        for derived_path, derived_original in derived_originals.items():
            self._restore_optional_bytes(derived_path, derived_original)
        if projection_replaced and generated_root.exists():
            shutil.rmtree(generated_root)
        if generated_existed and backup_root.exists():
            os.replace(backup_root, generated_root)

    def _stat_paths(self, catalog: Catalog) -> dict[str, StatEntry] | None:
        paths = {
            MANIFEST_FILENAME: self.skills_root / MANIFEST_FILENAME,
        }
        try:
            for child in self.skills_root.iterdir():
                if child != self.cache_path:
                    paths[child.name] = child
            collections = self._load_manifest()
            for collection in collections:
                collection_dir = self.skills_root / collection.name
                paths[collection.name] = collection_dir
                for child in collection_dir.iterdir():
                    paths[f"{collection.name}/{child.name}"] = child
            generated_root = self.skills_root / GENERATED_DIRECTORY
            paths[GENERATED_DIRECTORY] = generated_root
            for child in generated_root.iterdir():
                paths[f"{GENERATED_DIRECTORY}/{child.name}"] = child
            for entry in catalog.entries:
                paths[f"{entry.source_path}/SKILL.md"] = self.skills_root / entry.source_path / "SKILL.md"
            for projection in catalog.generated_projection.values():
                paths[f"{projection}/SKILL.md"] = self.skills_root / projection / "SKILL.md"
            return {name: StatEntry.from_file(path) for name, path in paths.items() if path != self.cache_path}
        except (CatalogError, OSError):
            return None

    def _update_cache(self, catalog: Catalog) -> None:
        stats = self._stat_paths(catalog)
        if stats is not None:
            StatCache(
                CACHE_SCHEMA_VERSION,
                str(self.skills_root),
                compute_content_hash((self.skills_root / CATALOG_FILENAME).read_text(encoding="utf-8")),
                stats,
            ).save(self.cache_path)

    def _slow_show(self, out: IO[str]) -> int:
        try:
            catalog, toc = self._full_refresh()
            self._publish(catalog, toc)
            self._update_cache(catalog)
        except CatalogError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        out.write(toc)
        return 0

    def show(self, out: IO[str] | None = None) -> int:
        out = out or sys.stdout
        catalog_path, toc_path = self.skills_root / CATALOG_FILENAME, self.skills_root / TOC_FILENAME
        catalog_text = catalog_path.read_text(encoding="utf-8") if catalog_path.is_file() else None
        catalog = Catalog.load(catalog_path)
        cache = StatCache.load(self.cache_path, self.skills_root)
        current = self._stat_paths(catalog) if catalog else None
        if (
            catalog is None
            or cache is None
            or catalog_text is None
            or not toc_path.is_file()
            or current is None
            or cache.catalog_hash != compute_content_hash(catalog_text)
            or cache.entries != current
        ):
            return self._slow_show(out)
        out.write(toc_path.read_text(encoding="utf-8"))
        return 0

    def update(self, out: IO[str] | None = None) -> int:
        return self._slow_show(out or sys.stdout)

    def check(self, out: IO[str] | None = None) -> int:
        out = out or sys.stdout
        try:
            catalog, toc = self._full_refresh()
            self._preflight_projection(catalog)
        except CatalogError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        issues: list[str] = []
        catalog_path, toc_path = self.skills_root / CATALOG_FILENAME, self.skills_root / TOC_FILENAME
        if not catalog_path.is_file() or catalog_path.read_text(encoding="utf-8") != catalog.as_json():
            issues.append("catalog.json is missing or stale")
        if not toc_path.is_file() or toc_path.read_text(encoding="utf-8") != toc:
            issues.append("TOC.md is missing or stale")
        for entry in catalog.entries:
            source_file, projection = (
                self.skills_root / entry.source_path / "SKILL.md",
                self.skills_root / catalog.generated_projection[entry.name] / "SKILL.md",
            )
            if compute_content_hash(source_file.read_text(encoding="utf-8")) != entry.content_hash:
                issues.append(f"{entry.source_path}/SKILL.md has a stale Updated date or content hash")
            if not projection.is_file() or projection.read_text(encoding="utf-8") != self._adapter_text(
                entry, catalog.generated
            ):
                issues.append(f"{catalog.generated_projection[entry.name]}/SKILL.md is missing or stale")
        if issues:
            print("\n".join(f"drift: {issue}" for issue in issues), file=sys.stderr)
            return 1
        out.write("ok: catalog is current\n")
        return 0


def _default_skills_root(vault_root: Path | None) -> Path:
    vault = vault_root or Path(os.environ.get("SECRET_AGENTS_VAULT_ROOT", Path.home() / "obsidian"))
    return vault.expanduser().resolve() / "handbag-of-holding" / "secret-agents" / "skills"


def main() -> int:
    parser = ArgumentParser(description="Validate and publish the secret-agents skill catalog")
    parser.add_argument("command", choices=["show", "update", "check"])
    parser.add_argument("--skills-root", type=Path)
    parser.add_argument("--vault-root", type=Path)
    arguments = parser.parse_args()
    skills_root = (arguments.skills_root or _default_skills_root(arguments.vault_root)).expanduser().resolve()
    if not skills_root.is_dir():
        print(f"error: skills source not found: {skills_root}; sync the vault or pass --vault-root", file=sys.stderr)
        return 2
    catalog = SkillCatalog(skills_root)
    return {"show": catalog.show, "update": catalog.update, "check": catalog.check}[arguments.command]()


if __name__ == "__main__":
    sys.exit(main())
