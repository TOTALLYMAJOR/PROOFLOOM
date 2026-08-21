from __future__ import annotations

from .assessment import assess_repository
from .linting import run_lint
from .models import ReviewVerdict, ValidationReport
from .repository import inspect_repository
from .reviewing import review_manifest


def validate_repository(root: str, review_data: dict | None = None) -> ValidationReport:
    snapshot = inspect_repository(root)
    assessment = assess_repository(root)
    lint_report = run_lint(root)
    review_report = review_manifest(review_data) if review_data else None
    status = _status(lint_report.status.value, review_report.verdict.value if review_report else None)
    notes = []
    if review_report is None:
        notes.append("No visual-review manifest supplied; validation covers repo-fit and deterministic linting only.")
    if assessment.runtime_strategy.value == "KEEP":
        notes.append("Validation confirms runtime restructure is not the default path here.")
    return ValidationReport(
        snapshot=snapshot,
        assessment=assessment,
        lint_report=lint_report,
        review_report=review_report,
        status=status,
        notes=notes,
    )


def _status(lint_status: str, review_status: str | None) -> ReviewVerdict:
    if lint_status == "FAIL" or review_status == "FAIL":
        return ReviewVerdict.FAIL
    if lint_status == "WARN" or review_status == "NEEDS_WORK":
        return ReviewVerdict.NEEDS_WORK
    return ReviewVerdict.PASS


def render_validation_text(report: ValidationReport) -> str:
    lines = [
        "VALIDATION",
        "",
        f"Status: {report.status.value}",
        f"Lint status: {report.lint_report.status.value}",
        f"Assessment posture: {report.assessment.structure_risk.value}",
    ]
    if report.review_report:
        lines.append(f"Review verdict: {report.review_report.verdict.value}")
    else:
        lines.append("Review verdict: NOT_RUN")
    if report.notes:
        lines.extend(["", "Notes:"])
        lines.extend(f"- {item}" for item in report.notes)
    return "\n".join(lines)
