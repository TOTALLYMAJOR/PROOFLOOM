from __future__ import annotations

from .linting import run_lint
from .models import DoctorReport, RepairCandidate, Severity
from .repository import inspect_repository


def run_doctor(root: str) -> DoctorReport:
    snapshot = inspect_repository(root)
    lint_report = run_lint(root)
    blockers = [
        "Competing repository authorities detected."
        for duplicate in snapshot.semantic_duplicates
        if duplicate.severity in {Severity.P0, Severity.P1}
    ]
    safe_repairs = [
        RepairCandidate(
            rule_id=finding.rule_id,
            severity=finding.severity,
            file=finding.file,
            line=finding.line,
            action=_repair_action(finding.rule_id),
            reason=finding.message,
        )
        for finding in lint_report.findings
        if finding.repairable and finding.severity in {Severity.P0, Severity.P1, Severity.P2}
    ][:3]
    notes = [
        "Doctor mode is read-only by default.",
        "Bounded repair planning may identify deterministic issues, but it must not weaken tests, baselines, or hide functionality.",
    ]
    return DoctorReport(
        snapshot=snapshot,
        lint_report=lint_report,
        blockers=blockers,
        safe_repairs=safe_repairs,
        bounded_repair_policy="Max 3 iterations; only deterministic P0/P1 and clear P2 issues; never weaken tests or thresholds.",
        notes=notes,
    )


def _repair_action(rule_id: str) -> str:
    actions = {
        "layout-unsafe-width": "Replace unsafe fixed width with a tokenized or responsive max-width strategy.",
        "layout-offscreen-position": "Remove off-screen positioning or replace it with an intentional responsive pattern.",
        "a11y-image-alt": "Add an intentional alt attribute based on the image's purpose.",
        "a11y-icon-button-name": "Add an explicit accessible name to the control.",
    }
    return actions.get(rule_id, "Resolve the deterministic issue without changing business behavior.")


def render_doctor_text(report: DoctorReport) -> str:
    lines = [
        "DOCTOR",
        "",
        f"Root: {report.snapshot.root}",
        f"Lint status: {report.lint_report.status.value}",
        "Blockers:",
    ]
    lines.extend(f"- {item}" for item in report.blockers or ["none"])
    lines.extend(["", "Safe repairs:"])
    if report.safe_repairs:
        for repair in report.safe_repairs:
            lines.append(
                f"- {repair.severity.value} {repair.file}:{repair.line} {repair.action}"
            )
    else:
        lines.append("- none")
    lines.extend(["", "Bounded repair policy:", report.bounded_repair_policy])
    if report.notes:
        lines.extend(["", "Notes:"])
        lines.extend(f"- {item}" for item in report.notes)
    return "\n".join(lines)
