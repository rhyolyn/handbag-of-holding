"""Parse, compare, and select immutable work-tracking evidence records."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from pathlib import Path
from typing import TypeAlias

import yaml

from .markdown import parse_opening_frontmatter, render_normalized_markdown
from .models import EvidenceDiagnostic, EvidenceRecord, EvidenceSelection, OutputDecision, ReportingWindow

_COMMON_FIELDS = (
    "kind",
    "occurred_start",
    "occurred_end",
    "source_system",
    "source_id",
    "initiatives",
    "tags",
    "status",
    "sources",
)
CommonValues: TypeAlias = tuple[str, date, date, str, str, tuple[str, ...], tuple[str, ...], str, tuple[str, ...]]
_PULL_REQUEST_URL = re.compile(r"^https://github\.com/[^/]+/[^/]+/pull/[1-9][0-9]*$")
_COMMIT_URL = re.compile(r"^https://github\.com/[^/]+/[^/]+/commit/[0-9a-fA-F]+$")
_REVIEW_URL = re.compile(r"^https://github\.com/[^/]+/[^/]+/pull/[1-9][0-9]*#pullrequestreview-[1-9][0-9]*$")


def parse_evidence(path: Path) -> EvidenceRecord | EvidenceDiagnostic:
    """Parse one evidence file into a record or a diagnostic that preserves its path."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError, ValueError, TypeError, yaml.YAMLError) as exc:
        return EvidenceDiagnostic(path, f"invalid YAML frontmatter: {exc}")
    return parse_evidence_text(path, text)


def parse_evidence_text(path: Path, text: str) -> EvidenceRecord | EvidenceDiagnostic:
    """Parse supplied evidence text while retaining the artifact path in diagnostics."""
    try:
        parsed = parse_opening_frontmatter(text)
        if parsed is None:
            return EvidenceDiagnostic(path, "frontmatter must open at the first line and contain a YAML mapping")
        frontmatter, body = parsed
        record_or_reason = _build_record(path, frontmatter, body)
    except (OSError, UnicodeError, ValueError, TypeError, yaml.YAMLError) as exc:
        return EvidenceDiagnostic(path, f"invalid YAML frontmatter: {exc}")
    if isinstance(record_or_reason, str):
        return EvidenceDiagnostic(path, record_or_reason)
    return record_or_reason


def decide_output(existing: EvidenceRecord | None, candidate: EvidenceRecord) -> OutputDecision:
    """Decide whether a candidate may create, skip, or conflict with existing evidence."""
    if existing is None:
        return OutputDecision.CREATE
    if existing.source_id != candidate.source_id:
        return OutputDecision.CONFLICT
    if existing.normalized_content == candidate.normalized_content:
        return OutputDecision.SKIP_IDENTICAL
    return OutputDecision.CONFLICT


def select_evidence(records: Iterable[EvidenceRecord], window: ReportingWindow) -> EvidenceSelection:
    """Select evidence that overlaps the inclusive-start, exclusive-end reporting window."""
    selected = tuple(record for record in records if _overlaps_window(record, window))
    return EvidenceSelection(selected, ())


def deduplicate_github(records: Iterable[EvidenceRecord]) -> tuple[EvidenceRecord, ...]:
    """Drop GitHub commits represented by an included merged pull request."""
    materialized_records = tuple(records)
    pr_commit_urls = frozenset().union(
        *(record.pr_commit_urls for record in materialized_records if record.source_system == "github")
    )
    return tuple(
        record
        for record in materialized_records
        if record.source_system != "github" or record.source_id not in pr_commit_urls
    )


def _build_record(path: Path, frontmatter: Mapping[object, object], body: str) -> EvidenceRecord | str:
    common_or_reason = _common_values(frontmatter)
    if isinstance(common_or_reason, str):
        return common_or_reason
    kind, occurred_start, occurred_end, source_system, source_id, initiatives, tags, status, sources = common_or_reason
    if occurred_end < occurred_start:
        return "occurred_end cannot precede occurred_start"
    commits_or_reason = _validate_source(kind, source_system, source_id, frontmatter)
    if isinstance(commits_or_reason, str):
        return commits_or_reason
    return EvidenceRecord(
        kind,
        occurred_start,
        occurred_end,
        source_system,
        source_id,
        initiatives,
        tags,
        status,
        sources,
        path,
        body,
        render_normalized_markdown(frontmatter, body),
        commits_or_reason,
    )


def _common_values(frontmatter: Mapping[object, object]) -> CommonValues | str:
    missing = [field for field in _COMMON_FIELDS if field not in frontmatter]
    if missing:
        return f"missing required frontmatter fields: {', '.join(missing)}"
    kind = _text_value(frontmatter["kind"])
    source_system = _text_value(frontmatter["source_system"])
    source_id = _text_value(frontmatter["source_id"])
    status = _text_value(frontmatter["status"])
    occurred_start = _date_value(frontmatter["occurred_start"])
    occurred_end = _date_value(frontmatter["occurred_end"])
    initiatives = _string_sequence(frontmatter["initiatives"])
    tags = _string_sequence(frontmatter["tags"])
    sources = _string_sequence(frontmatter["sources"])
    if (
        kind is None
        or source_system is None
        or source_id is None
        or status is None
        or occurred_start is None
        or occurred_end is None
        or initiatives is None
        or tags is None
        or sources is None
    ):
        return "common frontmatter fields have an invalid type or empty value"
    return kind, occurred_start, occurred_end, source_system, source_id, initiatives, tags, status, sources


def _validate_source(
    kind: str, source_system: str, source_id: str, frontmatter: Mapping[object, object]
) -> frozenset[str] | str:
    if source_system == "manual":
        return frozenset() if kind in {"work-receipt", "daily-note"} else "manual evidence has an invalid kind"
    if source_system == "perforce":
        return _validate_perforce(kind, source_id, frontmatter)
    if source_system == "github":
        return _validate_github(kind, source_id, frontmatter)
    return f"unsupported source_system {source_system!r}"


def _validate_perforce(kind: str, source_id: str, frontmatter: Mapping[object, object]) -> frozenset[str] | str:
    if kind != "source-control-receipt" or not source_id.isdigit():
        return "perforce evidence requires a source-control receipt and numeric changelist source_id"
    if frontmatter.get("changelist") != int(source_id):
        return "perforce evidence changelist must match its source_id"
    return frozenset()


def _validate_github(kind: str, source_id: str, frontmatter: Mapping[object, object]) -> frozenset[str] | str:
    if kind != "source-control-receipt":
        return "github evidence requires a source-control receipt"
    activity = _text_value(frontmatter.get("github_activity"))
    if activity is None:
        return "github evidence requires github_activity of merged_pull_request, commit, or review"
    if activity == "merged_pull_request":
        return _validate_merged_pull_request(source_id, frontmatter)
    if activity == "commit" and _is_commit_url(source_id):
        return _validate_non_pr_membership(frontmatter)
    if activity == "review" and _is_review_url(source_id):
        return _validate_non_pr_membership(frontmatter)
    return "github source_id does not match its github_activity"


def _validate_merged_pull_request(source_id: str, frontmatter: Mapping[object, object]) -> frozenset[str] | str:
    if not _is_pull_request_url(source_id):
        return "github source_id does not match its github_activity"
    if "pr_commit_urls" not in frontmatter:
        return "merged pull requests require pr_commit_urls membership metadata"
    commits = _string_sequence(frontmatter["pr_commit_urls"])
    if commits is None or not all(_is_commit_url(commit) for commit in commits):
        return "github pr_commit_urls must contain commit URLs"
    return frozenset(commits)


def _validate_non_pr_membership(frontmatter: Mapping[object, object]) -> frozenset[str] | str:
    commits = _string_sequence(frontmatter.get("pr_commit_urls", []))
    if commits is None or commits:
        return "only merged pull requests may include pr_commit_urls"
    return frozenset()


def _overlaps_window(record: EvidenceRecord, window: ReportingWindow) -> bool:
    return record.occurred_start < window.end_exclusive and record.occurred_end >= window.start


def _text_value(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _date_value(value: object) -> date | None:
    return value if isinstance(value, date) and not isinstance(value, datetime) else None


def _string_sequence(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return tuple(value)


def _is_pull_request_url(value: str) -> bool:
    return _PULL_REQUEST_URL.fullmatch(value) is not None


def _is_commit_url(value: str) -> bool:
    return _COMMIT_URL.fullmatch(value) is not None


def _is_review_url(value: str) -> bool:
    return _REVIEW_URL.fullmatch(value) is not None
