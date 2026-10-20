"""Regression contracts for combined work-tracking report inputs."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from secret_agents_work_tracking.evidence import parse_evidence
from secret_agents_work_tracking.models import (
    EvidenceDiagnostic,
    EvidenceRecord,
    OutputDecision,
    ReportingWindow,
    YearMonth,
)
from secret_agents_work_tracking.reporting import build_annual_input, build_month_input, build_status_input

EVIDENCE_FIXTURES = Path(__file__).parent / "fixtures" / "work_tracking" / "evidence"


def test_status_input_combines_all_evidence_kinds_with_complete_provenance(tmp_path: Path) -> None:
    manual = evidence("manual.md")
    daily = evidence("daily.md")
    perforce = evidence("perforce.md")
    pull_request = evidence("github-pr.md")
    included_commit = evidence("github-commit.md")
    review = evidence("github-review.md")
    diagnostic = EvidenceDiagnostic(tmp_path / "malformed.md", "invalid YAML")

    report = build_status_input(
        ReportingWindow(date(2026, 10, 16), date(2026, 10, 19)),
        tmp_path / "status.md",
        (manual, manual, daily, perforce, pull_request, included_commit, review),
        (diagnostic,),
    )

    assert report.sources == (
        manual.source_path,
        daily.source_path,
        perforce.source_path,
        pull_request.source_path,
        review.source_path,
    )
    assert report.source_links == tuple(f"[[{path.stem}]]" for path in report.sources)
    assert report.incomplete is True
    assert report.diagnostics == (diagnostic,)
    assert report.decision is OutputDecision.CREATE


def test_valid_empty_status_window_is_a_create_with_no_sources(tmp_path: Path) -> None:
    report = build_status_input(
        ReportingWindow(date(2026, 11, 1), date(2026, 11, 2)), tmp_path / "empty-status.md", (), ()
    )

    assert report.sources == ()
    assert report.incomplete is False
    assert report.decision is OutputDecision.CREATE


def test_monthly_input_consumes_only_status_reports_from_its_calendar_month(tmp_path: Path) -> None:
    october_status = build_status_input(
        ReportingWindow(date(2026, 10, 17), date(2026, 10, 18)),
        tmp_path / "status-october.md",
        (evidence("manual.md"),),
        (),
    )
    november_status = build_status_input(
        ReportingWindow(date(2026, 11, 1), date(2026, 11, 2)), tmp_path / "status-november.md", (), ()
    )

    monthly = build_month_input(YearMonth(2026, 10), tmp_path / "monthly-october.md", (october_status, november_status))

    assert monthly.sources == (october_status.output_path,)
    assert monthly.source_links == ("[[status-october]]",)
    assert monthly.incomplete is False


def test_living_annual_input_preserves_prior_months_and_adds_only_new_ones(tmp_path: Path) -> None:
    january = build_month_input(YearMonth(2026, 1), tmp_path / "monthly-2026-01.md", ())
    february = build_month_input(YearMonth(2026, 2), tmp_path / "monthly-2026-02.md", ())

    updated = build_annual_input(2026, tmp_path / "annual.md", (february,), (january.output_path,))
    unchanged = build_annual_input(2026, tmp_path / "annual.md", (january, february), updated.sources)

    assert updated.sources == (january.output_path, february.output_path)
    assert updated.decision is OutputDecision.CREATE
    assert unchanged.sources == updated.sources
    assert unchanged.decision is OutputDecision.SKIP_IDENTICAL


def test_annual_input_rejects_prior_sources_outside_its_year(tmp_path: Path) -> None:
    prior_source = tmp_path / "monthly-2025-12.md"

    report = build_annual_input(2026, tmp_path / "annual.md", (), (prior_source,))

    assert report.decision is OutputDecision.CONFLICT


def evidence(filename: str) -> EvidenceRecord:
    result = parse_evidence(EVIDENCE_FIXTURES / filename)
    assert isinstance(result, EvidenceRecord), result
    return result
