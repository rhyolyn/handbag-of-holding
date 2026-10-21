"""Build deterministic, source-provenanced inputs for combined work reports."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from pathlib import Path

from .evidence import deduplicate_github, select_evidence
from .models import EvidenceDiagnostic, EvidenceRecord, OutputDecision, ReportingWindow, ReportInput, YearMonth


def build_status_input(
    window: ReportingWindow,
    output_path: Path,
    records: Iterable[EvidenceRecord],
    diagnostics: Iterable[EvidenceDiagnostic],
) -> ReportInput:
    """Select all source-qualified evidence for one status-report window."""
    selected = select_evidence(deduplicate_github(records), window).records
    unique_records, duplicate_diagnostics = _unique_records(selected)
    all_diagnostics = tuple(diagnostics) + duplicate_diagnostics
    return _report_input(
        "status", window, output_path, (record.source_path for record in unique_records), all_diagnostics
    )


def build_month_input(year_month: YearMonth, output_path: Path, reports: Iterable[ReportInput]) -> ReportInput:
    """Select status reports ending in one calendar month for a monthly report."""
    selected = tuple(report for report in reports if _is_status_report_for_month(report, year_month))
    diagnostics = tuple(diagnostic for report in selected for diagnostic in report.diagnostics)
    return _report_input(
        "monthly", _month_window(year_month), output_path, (report.output_path for report in selected), diagnostics
    )


def build_annual_input(
    year: int, output_path: Path, reports: Iterable[ReportInput], previous_sources: Iterable[Path]
) -> ReportInput:
    """Preserve prior monthly evidence and append only newly available months for one annual review."""
    prior_sources = tuple(previous_sources)
    if any(not _is_monthly_source_for_year(path, year) for path in prior_sources):
        return _report_input("annual", _annual_window(year), output_path, prior_sources, (), OutputDecision.CONFLICT)
    monthly_reports = tuple(report for report in reports if _is_monthly_report_for_year(report, year))
    source_paths = _append_new_paths(prior_sources, (report.output_path for report in monthly_reports))
    diagnostics = tuple(diagnostic for report in monthly_reports for diagnostic in report.diagnostics)
    decision = OutputDecision.SKIP_IDENTICAL if source_paths == prior_sources else OutputDecision.CREATE
    return _report_input("annual", _annual_window(year), output_path, source_paths, diagnostics, decision)


def _unique_records(
    records: Iterable[EvidenceRecord],
) -> tuple[tuple[EvidenceRecord, ...], tuple[EvidenceDiagnostic, ...]]:
    unique: dict[str, EvidenceRecord] = {}
    diagnostics: list[EvidenceDiagnostic] = []
    for record in records:
        existing = unique.get(record.source_id)
        if existing is None:
            unique[record.source_id] = record
        elif existing.normalized_content != record.normalized_content:
            diagnostics.append(
                EvidenceDiagnostic(record.source_path, f"conflicting evidence for source_id {record.source_id}")
            )
    return tuple(unique.values()), tuple(diagnostics)


def _report_input(
    kind: str,
    window: ReportingWindow,
    output_path: Path,
    sources: Iterable[Path],
    diagnostics: tuple[EvidenceDiagnostic, ...],
    decision: OutputDecision = OutputDecision.CREATE,
) -> ReportInput:
    source_paths = tuple(sources)
    return ReportInput(
        kind,
        window,
        output_path,
        source_paths,
        tuple(_source_link(path) for path in source_paths),
        diagnostics,
        bool(diagnostics),
        decision,
    )


def _source_link(path: Path) -> str:
    return f"[[{path.stem}]]"


def _is_status_report_for_month(report: ReportInput, year_month: YearMonth) -> bool:
    return report.kind == "status" and (report.window.end_exclusive.year, report.window.end_exclusive.month) == (
        year_month.year,
        year_month.month,
    )


def _is_monthly_report_for_year(report: ReportInput, year: int) -> bool:
    return report.kind == "monthly" and report.window.start.year == year


def _month_window(year_month: YearMonth) -> ReportingWindow:
    start = date(year_month.year, year_month.month, 1)
    end = date(year_month.year + (year_month.month == 12), year_month.month % 12 + 1, 1)
    return ReportingWindow(start, end)


def _annual_window(year: int) -> ReportingWindow:
    return ReportingWindow(date(year, 1, 1), date(year + 1, 1, 1))


def _is_monthly_source_for_year(path: Path, year: int) -> bool:
    return path.stem.startswith(f"monthly-{year}-")


def _append_new_paths(existing: tuple[Path, ...], candidates: Iterable[Path]) -> tuple[Path, ...]:
    return existing + tuple(path for path in candidates if path not in existing)
