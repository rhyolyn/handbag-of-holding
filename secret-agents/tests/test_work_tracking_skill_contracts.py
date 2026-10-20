"""Regression contracts for portable work-tracking workflow instructions."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK_TRACKING_ROOT = ROOT / "skills" / "work-tracking"
TASK_FIVE_SKILLS = {
    "daily-note-create": "daily_notes",
    "perforce-receipt-create": "perforce_checkins",
    "perforce-receipt-range": "perforce_checkins",
    "perforce-rollup": "perforce_checkins",
    "report-cost-analysis": "ledgers",
    "report-receipt": "receipts",
}
TASK_SIX_SKILLS = {
    "git-receipt-create": "git_checkins",
    "git-receipt-range": "git_checkins",
    "git-rollup": "git_checkins",
}
REPORT_SKILLS = {
    "report-status": "status_reports",
    "report-rollup": "monthly_reports",
}
COMMON_FRONTMATTER_FIELDS = (
    "kind:",
    "occurred_start:",
    "occurred_end:",
    "source_system:",
    "source_id:",
    "initiatives:",
    "tags:",
    "status:",
    "sources:",
)
LEGACY_OUTPUT_PATH = re.compile(r"<(?:vault|worky-vault)>\\(?:Receipts|Checkins|Status Reports|Reviews)\\")


def test_perforce_workflows_replace_retired_checkin_source_directories() -> None:
    skill_names = canonical_skill_names()

    assert {"perforce-receipt-create", "perforce-receipt-range", "perforce-rollup"} <= skill_names
    assert not {"checkin-receipt-create", "checkin-receipt-range", "checkin-rollup"} & skill_names


def test_task_five_workflows_use_the_shared_resolver_and_named_locations() -> None:
    skills = canonical_skills()

    for name, location in TASK_FIVE_SKILLS.items():
        text = skills[name]
        assert "python -m secret_agents_work_tracking workspace check" in text
        assert f"`{location}`" in text


def test_git_workflows_use_the_shared_resolver_named_location_and_receipt_outputs() -> None:
    skills = canonical_skills()

    for name, location in TASK_SIX_SKILLS.items():
        text = skills[name]
        assert "python -m secret_agents_work_tracking workspace check" in text
        assert f"`{location}`" in text
    assert "merged pull request" in skills["git-receipt-create"].lower()
    assert "standalone commit" in skills["git-receipt-create"].lower()
    assert "review" in skills["git-receipt-create"].lower()
    assert "source receipts" in skills["git-rollup"].lower()


def test_report_workflows_use_combined_evidence_and_named_report_locations() -> None:
    skills = canonical_skills()

    for name, location in REPORT_SKILLS.items():
        assert "python -m secret_agents_work_tracking workspace check" in skills[name]
        assert f"`{location}`" in skills[name]
    assert "manual" in skills["report-status"].lower()
    assert "daily" in skills["report-status"].lower()
    assert "perforce" in skills["report-status"].lower()
    assert "github" in skills["report-status"].lower()
    assert "monthly reports" in skills["report-rollup"].lower()


def test_manual_and_daily_workflows_describe_the_common_evidence_frontmatter() -> None:
    skills = canonical_skills()

    for name in ("daily-note-create", "report-receipt"):
        assert all(field in skills[name] for field in COMMON_FRONTMATTER_FIELDS)


def test_hardcoded_legacy_output_path_guard_rejects_a_planted_violation(tmp_path: Path) -> None:
    planted = tmp_path / "SKILL.md"
    planted.write_text("Output: <vault>\\Receipts\\2026\\2026-10\\receipt.md", encoding="utf-8")

    assert hardcoded_legacy_output_paths((planted,)) == (planted,)


def test_hardcoded_legacy_output_path_guard_scans_live_work_tracking_skills() -> None:
    paths = tuple(WORK_TRACKING_ROOT.glob("*/SKILL.md"))

    assert paths
    assert hardcoded_legacy_output_paths(paths) == ()


def canonical_skill_names() -> set[str]:
    return {path.parent.name for path in WORK_TRACKING_ROOT.glob("*/SKILL.md")}


def canonical_skills() -> dict[str, str]:
    return {path.parent.name: path.read_text(encoding="utf-8") for path in WORK_TRACKING_ROOT.glob("*/SKILL.md")}


def hardcoded_legacy_output_paths(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    return tuple(path for path in paths if LEGACY_OUTPUT_PATH.search(path.read_text(encoding="utf-8")))
