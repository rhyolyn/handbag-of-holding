"""Inventory and validate classified legacy Worky artifacts without moving them."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Final

from .errors import MigrationPreflightError
from .evidence import parse_evidence
from .markdown import parse_opening_frontmatter
from .models import (
    EvidenceDiagnostic,
    EvidenceRecord,
    LocationName,
    MigrationEntry,
    MigrationInventory,
    MigrationPlan,
    Workspace,
)

_MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
_WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
_ROOT_CLASSIFICATIONS: Final[tuple[tuple[tuple[str, ...], LocationName, str, str], ...]] = (
    (("Receipts",), "receipts", "receipt", "legacy Receipts root"),
    (("Daily",), "daily_notes", "daily-note", "legacy Daily root"),
    (("Checkins", "perforce"), "perforce_checkins", "perforce-checkin", "legacy Checkins/perforce root"),
    (("Checkins", "git"), "git_checkins", "git-checkin", "legacy Checkins/git root"),
    (("Status Reports",), "status_reports", "status-report", "legacy Status Reports root"),
    (("Reviews", "Performance"), "annual_reviews", "annual-review", "legacy Reviews/Performance root"),
    (("Templates",), "templates", "template", "legacy Templates root"),
    (("Raw Imports",), "imports", "import", "legacy Raw Imports root"),
)
_EVIDENCE_CLASSIFICATIONS: Final = frozenset({"receipt", "daily-note", "perforce-checkin", "git-checkin"})


def build_inventory(workspace: Workspace) -> MigrationInventory:
    """Classify only known legacy artifacts without creating destination paths."""
    files = sorted(path for path in workspace.vault_root.rglob("*") if path.is_file())
    classified = tuple(entry for path in files if (entry := _classify_file(workspace, path)) is not None)
    classified_sources = {entry.source for entry in classified}
    untouched = tuple(path for path in files if path not in classified_sources and path.name != "work-tracking.yaml")
    return MigrationInventory(workspace, classified, untouched)


def preflight_migration(inventory: MigrationInventory) -> MigrationPlan:
    """Reject collisions, conflicting identities, or unresolved links before application."""
    _reject_destination_collisions(inventory.classified)
    _reject_conflicting_source_ids(inventory.classified)
    _reject_unresolved_links(inventory.workspace.vault_root, inventory.classified)
    return MigrationPlan(inventory)


def write_audit(plan: MigrationPlan, destination: Path) -> Path:
    """Write a deterministic read-only inventory audit to the caller-selected path."""
    payload = {
        "classified": [_entry_payload(entry) for entry in plan.inventory.classified],
        "untouched": [str(path) for path in plan.inventory.untouched],
    }
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def audit_payload(plan: MigrationPlan) -> dict[str, object]:
    """Render a preflight-approved plan without creating an audit file."""
    return {
        "mode": "dry-run",
        "classified": [_entry_payload(entry) for entry in plan.inventory.classified],
        "untouched": [str(path) for path in plan.inventory.untouched],
    }


def _classify_file(workspace: Workspace, path: Path) -> MigrationEntry | None:
    root_match = _root_classification(path.relative_to(workspace.vault_root))
    if root_match is not None:
        location, classification, rationale, relative = root_match
        return _inventory_entry(
            path,
            workspace.vault_root,
            workspace.location(location, require_exists=False) / relative,
            classification,
            rationale,
        )
    if "ledger" in path.name.casefold():
        return _inventory_entry(
            path,
            workspace.vault_root,
            workspace.location("ledgers", require_exists=False) / path.name,
            "ledger",
            "identified ledger filename",
        )
    return None


def _root_classification(relative: Path) -> tuple[LocationName, str, str, Path] | None:
    for root, location, classification, rationale in _ROOT_CLASSIFICATIONS:
        if relative.parts[: len(root)] == root:
            return location, classification, rationale, Path(*relative.parts[len(root) :])
    return None


def _inventory_entry(
    source: Path, vault_root: Path, destination: Path, classification: str, rationale: str
) -> MigrationEntry:
    content = source.read_bytes()
    content_hash = hashlib.sha256(content).hexdigest()
    return MigrationEntry(
        source, destination, classification, rationale, content_hash, _semantic_hash(source, vault_root, content)
    )


def _semantic_hash(source: Path, vault_root: Path, content: bytes) -> str:
    normalized = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    try:
        text = normalized.decode("utf-8")
    except UnicodeDecodeError:
        return hashlib.sha256(normalized).hexdigest()
    return hashlib.sha256(_semantic_text(source, vault_root, text).encode("utf-8")).hexdigest()


def _semantic_text(source: Path, vault_root: Path, text: str) -> str:
    parsed = parse_opening_frontmatter(text)
    body = text if parsed is None else parsed[1]
    body = _MARKDOWN_LINK.sub(lambda match: _canonical_markdown_link(source, vault_root, match), body)
    return _WIKILINK.sub(lambda match: _canonical_wikilink(vault_root, match), body)


def _canonical_markdown_link(source: Path, vault_root: Path, match: re.Match[str]) -> str:
    return f"[]({_resolved_target(vault_root, source, match.group(1))})"


def _canonical_wikilink(vault_root: Path, match: re.Match[str]) -> str:
    return f"[]({_resolved_target(vault_root, vault_root, match.group(1))})"


def _resolved_target(vault_root: Path, source: Path, target: str) -> str:
    relative_target = target.split("#", maxsplit=1)[0]
    direct = (source.parent / relative_target).resolve()
    if direct.is_file() and direct.is_relative_to(vault_root.resolve()):
        return str(direct)
    stem = Path(relative_target).stem
    matched = next((path.resolve() for path in vault_root.rglob("*.md") if path.stem == stem), None)
    return str(matched) if matched is not None else relative_target


def _reject_destination_collisions(entries: Iterable[MigrationEntry]) -> None:
    for entry in entries:
        if entry.destination.exists():
            raise MigrationPreflightError(f"destination already exists: {entry.destination}")


def _reject_conflicting_source_ids(entries: Iterable[MigrationEntry]) -> None:
    records = _evidence_records(entries)
    for record in records:
        for other in records:
            if record.source_path == other.source_path or record.source_id != other.source_id:
                continue
            if record.normalized_content != other.normalized_content:
                raise MigrationPreflightError(
                    f"conflicting source_id {record.source_id!r}: {record.source_path} and {other.source_path}"
                )


def _evidence_records(entries: Iterable[MigrationEntry]) -> tuple[EvidenceRecord, ...]:
    records: list[EvidenceRecord] = []
    for entry in entries:
        if entry.classification not in _EVIDENCE_CLASSIFICATIONS:
            continue
        parsed = parse_evidence(entry.source)
        if isinstance(parsed, EvidenceDiagnostic):
            raise MigrationPreflightError(f"malformed evidence {parsed.path}: {parsed.reason}")
        records.append(parsed)
    return tuple(records)


def _reject_unresolved_links(vault_root: Path, entries: Iterable[MigrationEntry]) -> None:
    for entry in entries:
        if entry.source.suffix.lower() != ".md":
            continue
        for target in _link_targets(entry.source):
            if not _resolves_link(vault_root, entry.source, target):
                raise MigrationPreflightError(f"unresolved link in {entry.source}: {target}")


def _link_targets(path: Path) -> tuple[str, ...]:
    text = path.read_text(encoding="utf-8")
    markdown = tuple(target.strip() for target in _MARKDOWN_LINK.findall(text))
    wikilinks = tuple(target.strip() for target in _WIKILINK.findall(text))
    return markdown + wikilinks


def _resolves_link(vault_root: Path, source: Path, target: str) -> bool:
    return Path(_resolved_target(vault_root, source, target)).is_file()


def _entry_payload(entry: MigrationEntry) -> dict[str, str]:
    return {
        "classification": entry.classification,
        "content_hash": entry.content_hash,
        "content_hash_algorithm": "sha256",
        "destination": str(entry.destination),
        "rationale": entry.rationale,
        "semantic_hash": entry.semantic_hash,
        "source": str(entry.source),
    }
