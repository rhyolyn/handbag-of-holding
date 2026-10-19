"""Inventory and validate classified legacy Worky artifacts without moving them."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, date, datetime
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import Final

from .errors import MigrationPreflightError
from .evidence import parse_evidence_text
from .markdown import parse_opening_frontmatter, render_normalized_markdown
from .models import (
    EvidenceDiagnostic,
    EvidenceRecord,
    LocationName,
    MigrationAudit,
    MigrationEntry,
    MigrationInventory,
    MigrationMove,
    MigrationPlan,
    Workspace,
)

_MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
_WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
_CODE_LITERAL = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)
_DATE_IN_FILENAME = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)")
_DATE_IN_DAILY_HEADING = re.compile(r"^#\s+(\d{4}-\d{2}-\d{2})(?:\s|$)", re.MULTILINE)
_ISO_DATE_WIKILINK_PLACEHOLDER = re.compile(r"^(?:YYYY|yyyy)-MM-DD$")
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


def apply_migration(plan: MigrationPlan) -> MigrationAudit:
    """Apply one preflight-approved migration and roll back on the first failure."""
    workspace = plan.inventory.workspace
    journal = _write_journal(workspace, plan)
    completed: list[_AppliedEntry] = []
    target_map = {entry.source.resolve(): entry.destination for entry in plan.inventory.classified}
    try:
        for entry in plan.inventory.classified:
            completed.append(_apply_entry(entry, workspace.vault_root, target_map))
    except OSError as exc:
        _rollback_entries(completed)
        audit = MigrationAudit((), (str(exc),), plan.inventory.untouched)
        _write_failure_audit(journal, audit)
        return audit
    audit = _successful_audit(completed, plan.inventory.untouched)
    _remove_backups(completed)
    _write_success_audit(workspace, audit)
    journal.unlink(missing_ok=True)
    return audit


def write_applied_audit(audit: MigrationAudit, destination: Path) -> Path:
    """Write one completed migration audit to a caller-selected path."""
    destination.write_text(_audit_json(audit), encoding="utf-8")
    return destination


def applied_audit_payload(audit: MigrationAudit) -> dict[str, object]:
    """Render an applied migration result for the command boundary."""
    return _audit_data(audit)


def _write_journal(workspace: Workspace, plan: MigrationPlan) -> Path:
    journal = workspace.location("ledgers", require_exists=False) / "migration-journal.json"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(json.dumps(audit_payload(plan), sort_keys=True), encoding="utf-8")
    return journal


def _apply_entry(entry: MigrationEntry, vault_root: Path, target_map: dict[Path, Path]) -> _AppliedEntry:
    if entry.destination.exists():
        raise OSError(f"destination already exists: {entry.destination}")
    entry.destination.parent.mkdir(parents=True, exist_ok=True)
    if entry.source.suffix.lower() != ".md":
        os.rename(entry.source, entry.destination)
        return _AppliedEntry(entry, None, ())
    content, rewritten_links = _rewritten_document(entry, vault_root, target_map)
    staging = _write_staged_document(entry.destination, content)
    backup = entry.source.with_name(f"{entry.source.name}.migration-backup")
    try:
        os.rename(entry.source, backup)
        os.rename(staging, entry.destination)
    except OSError:
        _restore_unfinished_entry(entry.source, backup, staging)
        raise
    return _AppliedEntry(entry, backup, rewritten_links)


def _write_staged_document(destination: Path, content: str) -> Path:
    staging = destination.with_name(f".{destination.name}.staging")
    staging.write_text(content, encoding="utf-8")
    return staging


def _restore_unfinished_entry(source: Path, backup: Path, staging: Path) -> None:
    staging.unlink(missing_ok=True)
    if backup.exists() and not source.exists():
        os.rename(backup, source)


def _rewritten_document(
    entry: MigrationEntry, vault_root: Path, target_map: dict[Path, Path]
) -> tuple[str, tuple[str, ...]]:
    source = entry.source
    text = _normalized_migration_document(entry)
    markdown = _replace_links_outside_code(
        text, _MARKDOWN_LINK, lambda match: _rewrite_markdown_link(source, vault_root, target_map, match)
    )
    rewritten = _replace_links_outside_code(
        markdown, _WIKILINK, lambda match: _rewrite_wikilink(vault_root, target_map, match)
    )
    return rewritten, tuple(sorted(set(_link_targets(source))))


def _rewrite_markdown_link(source: Path, vault_root: Path, target_map: dict[Path, Path], match: re.Match[str]) -> str:
    target = _migration_target(vault_root, source, match.group(1), target_map)
    if target is None:
        return match.group(0)
    label = match.group(0)[1 : match.group(0).index("](")]
    return f"[{label}]({target})"


def _rewrite_wikilink(vault_root: Path, target_map: dict[Path, Path], match: re.Match[str]) -> str:
    target = _migration_target(vault_root, vault_root, match.group(1), target_map)
    return match.group(0) if target is None else f"[[{target}]]"


def _migration_target(vault_root: Path, source: Path, raw_target: str, target_map: dict[Path, Path]) -> str | None:
    resolved = _planned_link_target(vault_root, source, raw_target, target_map)
    destination = target_map.get(resolved)
    if destination is None:
        return None
    return destination.relative_to(vault_root).as_posix()


def _planned_link_target(vault_root: Path, source: Path, raw_target: str, target_map: dict[Path, Path]) -> Path:
    direct = (source.parent / raw_target.split("#", maxsplit=1)[0]).resolve()
    if direct in target_map:
        return direct
    return Path(_resolved_target(vault_root, source, raw_target)).resolve()


def _rollback_entries(entries: list[_AppliedEntry]) -> None:
    for applied in reversed(entries):
        if applied.backup is None:
            os.rename(applied.entry.destination, applied.entry.source)
            continue
        applied.entry.destination.unlink(missing_ok=True)
        os.rename(applied.backup, applied.entry.source)


def _successful_audit(entries: list[_AppliedEntry], untouched: tuple[Path, ...]) -> MigrationAudit:
    moved = tuple(
        MigrationMove(
            entry.entry.source,
            entry.entry.destination,
            entry.entry.content_hash,
            hashlib.sha256(entry.entry.destination.read_bytes()).hexdigest(),
            entry.rewritten_links,
        )
        for entry in entries
    )
    return MigrationAudit(moved, (), untouched)


def _remove_backups(entries: list[_AppliedEntry]) -> None:
    for entry in entries:
        if entry.backup is not None:
            entry.backup.unlink(missing_ok=True)


def _write_failure_audit(journal: Path, audit: MigrationAudit) -> None:
    journal.with_name("migration-audit-failed.json").write_text(_audit_json(audit), encoding="utf-8")


def _write_success_audit(workspace: Workspace, audit: MigrationAudit) -> None:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = workspace.location("ledgers", require_exists=False) / f"migration-audit-{timestamp}.json"
    path.write_text(_audit_json(audit), encoding="utf-8")


def _audit_json(audit: MigrationAudit) -> str:
    return json.dumps(_audit_data(audit), indent=2, sort_keys=True) + "\n"


def _audit_data(audit: MigrationAudit) -> dict[str, object]:
    return {
        "moved": [_move_payload(move) for move in audit.moved],
        "unresolved": list(audit.unresolved),
        "untouched": [str(path) for path in audit.untouched],
    }


def _move_payload(move: MigrationMove) -> dict[str, object]:
    return {
        "content_hash": move.content_hash,
        "content_hash_algorithm": "sha256",
        "destination": str(move.destination),
        "output_hash": move.output_hash,
        "rewritten_links": list(move.rewritten_links),
        "source": str(move.source),
    }


class _AppliedEntry:
    """Retain rollback-only state until the migration transaction commits."""

    def __init__(self, entry: MigrationEntry, backup: Path | None, rewritten_links: tuple[str, ...]) -> None:
        self.entry = entry
        self.backup = backup
        self.rewritten_links = rewritten_links


def _classify_file(workspace: Workspace, path: Path) -> MigrationEntry | None:
    relative_path = path.relative_to(workspace.vault_root)
    if _is_top_level_perforce_operational_file(relative_path):
        return None
    if _is_unclassifiable_legacy_daily_note(relative_path, path):
        return None
    if _is_unclassifiable_legacy_receipt(relative_path, path):
        return None
    if _is_legacy_perforce_rollup(relative_path):
        return _inventory_entry(
            path,
            workspace.vault_root,
            workspace.location("perforce_checkins", require_exists=False) / Path(*relative_path.parts[2:]),
            "perforce-rollup",
            "legacy Checkins/perforce rollup",
        )
    root_match = _root_classification(relative_path)
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


def _is_top_level_perforce_operational_file(relative_path: Path) -> bool:
    return len(relative_path.parts) == 3 and relative_path.parts[:2] == ("Checkins", "perforce")


def _is_unclassifiable_legacy_daily_note(relative_path: Path, path: Path) -> bool:
    if relative_path.parts[:1] != ("Daily",):
        return False
    text = path.read_text(encoding="utf-8")
    return parse_opening_frontmatter(text) is None and _daily_note_date(path, text) is None


def _is_unclassifiable_legacy_receipt(relative_path: Path, path: Path) -> bool:
    if relative_path.parts[:1] != ("Receipts",):
        return False
    text = path.read_text(encoding="utf-8")
    return parse_opening_frontmatter(text) is None and _receipt_date_range(path) is None


def _is_legacy_perforce_rollup(relative_path: Path) -> bool:
    return (
        len(relative_path.parts) >= 6
        and relative_path.parts[:2] == ("Checkins", "perforce")
        and relative_path.parts[4] == "rollups"
    )


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
    markdown = _replace_links_outside_code(
        body, _MARKDOWN_LINK, lambda match: _canonical_markdown_link(source, vault_root, match)
    )
    return _replace_links_outside_code(markdown, _WIKILINK, lambda match: _canonical_wikilink(vault_root, match))


def _canonical_markdown_link(source: Path, vault_root: Path, match: re.Match[str]) -> str:
    return f"[]({_resolved_target(vault_root, source, match.group(1))})"


def _canonical_wikilink(vault_root: Path, match: re.Match[str]) -> str:
    target = match.group(1)
    if _is_iso_date_wikilink_placeholder(target):
        return match.group(0)
    return f"[]({_resolved_target(vault_root, vault_root, target)})"


def _resolved_target(vault_root: Path, source: Path, target: str) -> str:
    relative_target = target.split("#", maxsplit=1)[0]
    direct = (source.parent / relative_target).resolve()
    if direct.is_file() and direct.is_relative_to(vault_root.resolve()):
        return str(direct)
    stem = Path(relative_target).stem
    matched = _markdown_paths_by_stem(vault_root).get(stem)
    return str(matched) if matched is not None else relative_target


@cache
def _markdown_paths_by_stem(vault_root: Path) -> Mapping[str, Path]:
    paths_by_stem: dict[str, Path] = {}
    for path in vault_root.rglob("*.md"):
        paths_by_stem.setdefault(path.stem, path.resolve())
    return MappingProxyType(paths_by_stem)


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
        parsed = parse_evidence_text(entry.source, _normalized_migration_document(entry))
        if isinstance(parsed, EvidenceDiagnostic):
            raise MigrationPreflightError(f"malformed evidence {parsed.path}: {parsed.reason}")
        records.append(parsed)
    return tuple(records)


def _normalized_migration_document(entry: MigrationEntry) -> str:
    text = entry.source.read_text(encoding="utf-8")
    if entry.classification == "daily-note":
        return _normalize_legacy_daily_note(entry, text)
    if entry.classification == "receipt":
        return _normalize_legacy_receipt(entry, text)
    if entry.classification != "perforce-checkin":
        return text
    parsed = parse_opening_frontmatter(text)
    if parsed is None:
        return text
    frontmatter, body = parsed
    changelist = frontmatter.get("cl")
    occurred_on = frontmatter.get("date")
    initiative = frontmatter.get("arc")
    if not _is_legacy_perforce_receipt(frontmatter, changelist, occurred_on, initiative):
        return text
    normalized = dict(frontmatter)
    normalized.update(
        {
            "kind": "source-control-receipt",
            "occurred_start": occurred_on,
            "occurred_end": occurred_on,
            "source_system": "perforce",
            "source_id": str(changelist),
            "initiatives": [initiative],
            "sources": [],
        }
    )
    normalized.setdefault("changelist", changelist)
    return render_normalized_markdown(normalized, body)


def _normalize_legacy_daily_note(entry: MigrationEntry, text: str) -> str:
    if parse_opening_frontmatter(text) is not None:
        return text
    occurred_on = _daily_note_date(entry.source, text)
    if occurred_on is None:
        return text
    return render_normalized_markdown(
        _manual_migration_frontmatter("daily-note", occurred_on, occurred_on, entry), text
    )


def _normalize_legacy_receipt(entry: MigrationEntry, text: str) -> str:
    if parse_opening_frontmatter(text) is not None:
        return text
    date_range = _receipt_date_range(entry.source)
    if date_range is None:
        return text
    occurred_start, occurred_end = date_range
    return render_normalized_markdown(
        _manual_migration_frontmatter("work-receipt", occurred_start, occurred_end, entry), text
    )


def _manual_migration_frontmatter(
    kind: str, occurred_start: date, occurred_end: date, entry: MigrationEntry
) -> dict[object, object]:
    return {
        "kind": kind,
        "occurred_start": occurred_start,
        "occurred_end": occurred_end,
        "source_system": "manual",
        "source_id": f"manual:migration:{entry.content_hash}",
        "initiatives": [],
        "tags": [],
        "status": "draft",
        "sources": [],
    }


def _daily_note_date(source: Path, text: str) -> date | None:
    candidates = tuple(
        candidate for candidate in (_filename_date(source), _heading_date(text)) if candidate is not None
    )
    if not candidates:
        return None
    directory_month = _daily_note_directory_month(source)
    scores = {
        candidate: candidates.count(candidate) + int(directory_month == candidate.strftime("%Y-%m"))
        for candidate in candidates
    }
    highest_score = max(scores.values())
    winners = tuple(candidate for candidate, score in scores.items() if score == highest_score)
    return winners[0] if highest_score >= 2 and len(winners) == 1 else None


def _filename_date(source: Path) -> date | None:
    matches = _DATE_IN_FILENAME.findall(source.name)
    return _parse_single_date(matches)


def _heading_date(text: str) -> date | None:
    match = _DATE_IN_DAILY_HEADING.search(text)
    return None if match is None else _parse_single_date((match.group(1),))


def _parse_single_date(values: tuple[str, ...] | list[str]) -> date | None:
    if len(values) != 1:
        return None
    try:
        return date.fromisoformat(values[0])
    except ValueError:
        return None


def _daily_note_directory_month(source: Path) -> str | None:
    month = source.parent.name
    if source.parent.parent.name != month[:4] or len(month) != 7:
        return None
    try:
        date.fromisoformat(f"{month}-01")
    except ValueError:
        return None
    return month


def _receipt_date_range(source: Path) -> tuple[date, date] | None:
    date_values = _DATE_IN_FILENAME.findall(source.name)
    if len(date_values) not in {1, 2}:
        return None
    try:
        dates = tuple(date.fromisoformat(value) for value in date_values)
    except ValueError:
        return None
    if dates[-1] < dates[0]:
        return None
    return dates[0], dates[-1]


def _is_legacy_perforce_receipt(
    frontmatter: object, changelist: object, occurred_on: object, initiative: object
) -> bool:
    if not isinstance(frontmatter, dict) or frontmatter.get("source") not in (None, "perforce"):
        return False
    if any(
        field in frontmatter
        for field in ("kind", "occurred_start", "occurred_end", "source_system", "source_id", "initiatives", "sources")
    ):
        return False
    return (
        isinstance(changelist, int)
        and not isinstance(changelist, bool)
        and isinstance(occurred_on, date)
        and not isinstance(occurred_on, datetime)
        and isinstance(initiative, str)
        and bool(initiative)
    )


def _reject_unresolved_links(vault_root: Path, entries: Iterable[MigrationEntry]) -> None:
    for entry in entries:
        if entry.source.suffix.lower() != ".md":
            continue
        text = entry.source.read_text(encoding="utf-8")
        for target in _markdown_link_targets(text):
            if _is_external_markdown_link(target):
                continue
            if not _resolves_link(vault_root, entry.source, target):
                raise MigrationPreflightError(f"unresolved link in {entry.source}: {target}")
        for target in _wikilink_targets(text):
            if not _resolves_link(vault_root, entry.source, target):
                raise MigrationPreflightError(f"unresolved link in {entry.source}: {target}")


def _link_targets(path: Path) -> tuple[str, ...]:
    text = path.read_text(encoding="utf-8")
    return _markdown_link_targets(text) + _wikilink_targets(text)


def _markdown_link_targets(text: str) -> tuple[str, ...]:
    return tuple(target.strip() for target in _MARKDOWN_LINK.findall(_text_outside_code_literals(text)))


def _wikilink_targets(text: str) -> tuple[str, ...]:
    return tuple(
        target
        for match in _WIKILINK.findall(_text_outside_code_literals(text))
        if not _is_iso_date_wikilink_placeholder(target := match.strip())
    )


def _is_iso_date_wikilink_placeholder(target: str) -> bool:
    return bool(_ISO_DATE_WIKILINK_PLACEHOLDER.fullmatch(target))


def _text_outside_code_literals(text: str) -> str:
    return _CODE_LITERAL.sub("", text)


def _replace_links_outside_code(
    text: str, pattern: re.Pattern[str], replacement: Callable[[re.Match[str]], str]
) -> str:
    pieces: list[str] = []
    cursor = 0
    for code_literal in _CODE_LITERAL.finditer(text):
        pieces.append(pattern.sub(replacement, text[cursor : code_literal.start()]))
        pieces.append(code_literal.group(0))
        cursor = code_literal.end()
    pieces.append(pattern.sub(replacement, text[cursor:]))
    return "".join(pieces)


def _resolves_link(vault_root: Path, source: Path, target: str) -> bool:
    return Path(_resolved_target(vault_root, source, target)).is_file()


def _is_external_markdown_link(target: str) -> bool:
    path = target.split("#", maxsplit=1)[0]
    return (
        "://" in path
        or path.startswith("mailto:")
        or path.startswith("/")
        or ("/" in path and not path.startswith(("./", "../", "/")))
        or (Path(path).suffix == "" and not path.startswith((".", "/")))
    )


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
