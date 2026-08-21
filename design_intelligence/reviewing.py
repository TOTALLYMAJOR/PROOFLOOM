from __future__ import annotations

from .models import ReviewFinding, ReviewReport, ReviewVerdict, Severity


def review_manifest(manifest: dict) -> ReviewReport:
    surface = manifest.get("surface", "Unnamed surface")
    items = manifest.get("viewport_findings", []) or manifest.get("findings", [])
    findings = [
        ReviewFinding(
            surface=surface,
            viewport=item.get("viewport", "unknown"),
            severity=Severity(item.get("severity", "P2")),
            root_cause=item.get("root_cause", "visual"),
            evidence=item.get("evidence", "No evidence supplied."),
            preserve=item.get("preserve", []),
            change=item.get("change", []),
            repairable=bool(item.get("repairable", False)),
            source=item.get("source", manifest.get("source", "manual")),
        )
        for item in items
    ]
    covered_viewports = sorted({finding.viewport for finding in findings})
    remaining_debt = manifest.get("remaining_debt", [])
    verdict = _verdict(findings, covered_viewports)
    notes = []
    if "desktop" not in covered_viewports or "mobile" not in covered_viewports:
        notes.append("Material UI work should validate both desktop and mobile; one viewport is missing.")
    if not findings:
        notes.append("No visual findings were supplied; this is only a placeholder review.")
    return ReviewReport(
        surface=surface,
        verdict=verdict,
        findings=findings,
        covered_viewports=covered_viewports,
        remaining_debt=remaining_debt,
        notes=notes,
    )


def _verdict(findings: list[ReviewFinding], covered_viewports: list[str]) -> ReviewVerdict:
    severities = {finding.severity for finding in findings}
    if Severity.P0 in severities or Severity.P1 in severities:
        return ReviewVerdict.FAIL
    if findings or len(covered_viewports) < 2:
        return ReviewVerdict.NEEDS_WORK
    return ReviewVerdict.PASS


def render_review_text(report: ReviewReport) -> str:
    lines = [
        "VISUAL REVIEW",
        "",
        f"Surface: {report.surface}",
        f"Verdict: {report.verdict.value}",
        f"Covered viewports: {', '.join(report.covered_viewports) or 'none'}",
        "",
        "Findings:",
    ]
    if report.findings:
        for finding in report.findings:
            lines.append(
                f"- {finding.severity.value} {finding.viewport} {finding.root_cause}: {finding.evidence}"
            )
    else:
        lines.append("- none")
    if report.remaining_debt:
        lines.extend(["", "Remaining debt:"])
        lines.extend(f"- {item}" for item in report.remaining_debt)
    if report.notes:
        lines.extend(["", "Notes:"])
        lines.extend(f"- {item}" for item in report.notes)
    return "\n".join(lines)
