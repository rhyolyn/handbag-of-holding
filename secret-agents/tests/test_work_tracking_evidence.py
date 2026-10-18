"""Evidence parsing, identity, and selection contracts."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from secret_agents_work_tracking.evidence import decide_output, deduplicate_github, parse_evidence, select_evidence
from secret_agents_work_tracking.models import EvidenceDiagnostic, EvidenceRecord, OutputDecision, ReportingWindow

FIXTURES = Path(__file__).parent / "fixtures" / "work_tracking" / "evidence"


@pytest.mark.parametrize(
    ("filename", "source_system", "expected_pr_commits"),
    [
        ("manual.md", "manual", frozenset()),
        ("daily.md", "manual", frozenset()),
        ("perforce.md", "perforce", frozenset()),
        ("github-pr.md", "github", frozenset({"https://github.com/acme/work-tracking/commit/abc123"})),
        ("github-commit.md", "github", frozenset()),
        ("github-review.md", "github", frozenset()),
    ],
)
def test_parse_evidence_validates_each_source_contract(
    filename: str, source_system: str, expected_pr_commits: frozenset[str]
) -> None:
    result = parse_evidence(FIXTURES / filename)

    assert isinstance(result, EvidenceRecord)
    assert result.source_system == source_system
    assert result.pr_commit_urls == expected_pr_commits


def test_identical_stable_identity_skips_and_different_content_conflicts(tmp_path: Path) -> None:
    original = evidence("manual.md")
    identical_path = tmp_path / "identical.md"
    identical_path.write_text((FIXTURES / "manual.md").read_text(encoding="utf-8"), encoding="utf-8")
    changed_path = tmp_path / "changed.md"
    changed_path.write_text(
        (FIXTURES / "manual.md").read_text(encoding="utf-8").replace("Defined", "Revised"), encoding="utf-8"
    )

    assert decide_output(original, evidence_path(identical_path)) is OutputDecision.SKIP_IDENTICAL
    assert decide_output(original, evidence_path(changed_path)) is OutputDecision.CONFLICT


def test_normalized_identity_ignores_yaml_key_order_and_line_endings(tmp_path: Path) -> None:
    reordered_path = tmp_path / "reordered.md"
    reordered_path.write_bytes(
        b"---\r\n"
        b"tags: [architecture]\r\n"
        b"source_id: manual:2026-10-17:workspace-contract\r\n"
        b"kind: work-receipt\r\n"
        b"sources: []\r\n"
        b"occurred_end: 2026-10-17\r\n"
        b"initiatives: [Work Tracking]\r\n"
        b"source_system: manual\r\n"
        b"status: draft\r\n"
        b"occurred_start: 2026-10-17\r\n"
        b"---\r\n"
        b"# Workspace contract\r\n\r\nDefined the workspace contract.\r\n"
    )

    assert decide_output(evidence("manual.md"), evidence_path(reordered_path)) is OutputDecision.SKIP_IDENTICAL


def test_selection_uses_an_inclusive_start_and_exclusive_end() -> None:
    records = (evidence("manual.md"), evidence("perforce.md"), evidence("daily.md"))

    selection = select_evidence(records, ReportingWindow(date(2026, 10, 17), date(2026, 10, 18)))

    assert [record.source_id for record in selection.records] == ["manual:2026-10-17:workspace-contract", "12345"]
    assert selection.diagnostics == ()


def test_merged_pull_request_absorbs_its_included_commit() -> None:
    pull_request = evidence("github-pr.md")
    commit = evidence("github-commit.md")
    review = evidence("github-review.md")

    deduplicated = deduplicate_github((pull_request, commit, review))

    assert [record.source_id for record in deduplicated] == [pull_request.source_id, review.source_id]


def test_malformed_yaml_returns_a_path_bearing_diagnostic() -> None:
    result = parse_evidence(FIXTURES / "malformed.md")

    assert isinstance(result, EvidenceDiagnostic)
    assert result.path == FIXTURES / "malformed.md"
    assert "YAML" in result.reason


@pytest.mark.parametrize(
    ("filename", "content", "reason"),
    [
        ("invalid-date.md", b"---\noccurred_start: 2026-13-17\n", "YAML"),
        ("invalid-activity.md", None, "github_activity"),
        ("invalid-utf8.md", b"\xff\xfe", "YAML"),
    ],
)
def test_malformed_evidence_always_returns_a_path_bearing_diagnostic(
    tmp_path: Path, filename: str, content: bytes | None, reason: str
) -> None:
    path = tmp_path / filename
    if content is None:
        content = (
            (FIXTURES / "github-pr.md")
            .read_text(encoding="utf-8")
            .replace("github_activity: merged_pull_request", "github_activity: [merged_pull_request]")
            .encode()
        )
    path.write_bytes(content)

    result = parse_evidence(path)

    assert isinstance(result, EvidenceDiagnostic)
    assert result.path == path
    assert reason in result.reason


def test_perforce_source_id_must_match_a_numeric_changelist(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid-perforce.md"
    invalid_path.write_text(
        (FIXTURES / "perforce.md").read_text(encoding="utf-8").replace('source_id: "12345"', 'source_id: "abc"'),
        encoding="utf-8",
    )

    result = parse_evidence(invalid_path)

    assert isinstance(result, EvidenceDiagnostic)
    assert "numeric changelist" in result.reason


def test_evidence_end_date_cannot_precede_its_start_date(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid-dates.md"
    invalid_path.write_text(
        (FIXTURES / "manual.md")
        .read_text(encoding="utf-8")
        .replace("occurred_end: 2026-10-17", "occurred_end: 2026-10-16"),
        encoding="utf-8",
    )

    result = parse_evidence(invalid_path)

    assert isinstance(result, EvidenceDiagnostic)
    assert "occurred_end" in result.reason


def test_github_activity_requires_a_valid_activity_specific_identity(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid-github.md"
    invalid_path.write_text(
        (FIXTURES / "github-pr.md")
        .read_text(encoding="utf-8")
        .replace("https://github.com/acme/work-tracking/pull/42", "https://github.com/", 1),
        encoding="utf-8",
    )

    result = parse_evidence(invalid_path)

    assert isinstance(result, EvidenceDiagnostic)
    assert "source_id" in result.reason


def test_merged_pull_request_requires_commit_membership_metadata(tmp_path: Path) -> None:
    invalid_path = tmp_path / "missing-membership.md"
    invalid_path.write_text(
        (FIXTURES / "github-pr.md")
        .read_text(encoding="utf-8")
        .replace("pr_commit_urls:\n  - https://github.com/acme/work-tracking/commit/abc123\n", ""),
        encoding="utf-8",
    )

    result = parse_evidence(invalid_path)

    assert isinstance(result, EvidenceDiagnostic)
    assert "pr_commit_urls" in result.reason


def test_pull_request_membership_accepts_only_commit_urls(tmp_path: Path) -> None:
    invalid_path = tmp_path / "review-membership.md"
    invalid_path.write_text(
        (FIXTURES / "github-pr.md")
        .read_text(encoding="utf-8")
        .replace(
            "https://github.com/acme/work-tracking/commit/abc123",
            "https://github.com/acme/work-tracking/pull/42#pullrequestreview-9",
        ),
        encoding="utf-8",
    )

    result = parse_evidence(invalid_path)

    assert isinstance(result, EvidenceDiagnostic)
    assert "commit URLs" in result.reason


def evidence(filename: str) -> EvidenceRecord:
    return evidence_path(FIXTURES / filename)


def evidence_path(path: Path) -> EvidenceRecord:
    result = parse_evidence(path)
    assert isinstance(result, EvidenceRecord), result
    return result
