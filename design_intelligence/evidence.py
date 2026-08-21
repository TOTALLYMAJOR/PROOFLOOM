from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import EvidencePack, RepositoryAssessment, ReviewReport, ValidationReport


def build_evidence_pack(
    assessment: RepositoryAssessment,
    validation: ValidationReport,
    contract: dict[str, Any] | None = None,
    review_manifest: dict[str, Any] | None = None,
    quality_report: dict[str, Any] | None = None,
    memory_context: dict[str, Any] | None = None,
) -> EvidencePack:
    review = validation.review_report
    before = list((review_manifest or {}).get("before_screenshots", []))
    after = list((review_manifest or {}).get("after_screenshots", []))
    lint_summary = {
        "status": validation.lint_report.status.value,
        "counts": validation.lint_report.counts,
        "top_findings": [finding.to_dict() for finding in validation.lint_report.findings[:5]],
    }
    review_summary = (
        {
            "verdict": review.verdict.value,
            "covered_viewports": review.covered_viewports,
            "top_findings": [finding.to_dict() for finding in review.findings[:5]],
        }
        if review
        else {"verdict": "NOT_RUN", "covered_viewports": [], "top_findings": []}
    )
    decision_summary = (
        f"{assessment.recommendation.value} with {assessment.structure_risk.value} posture; "
        f"knowledge strategy {assessment.knowledge_strategy.value}, runtime strategy {assessment.runtime_strategy.value}."
    )
    known_debt = list(validation.lint_report.notes)
    if review:
        known_debt.extend(review.remaining_debt)
    return EvidencePack(
        contract=contract or {},
        repo_context=assessment.to_dict(),
        before_screenshots=before,
        after_screenshots=after,
        lint_summary=lint_summary,
        review_summary=review_summary,
        decision_summary=decision_summary,
        known_debt=known_debt,
        quality_summary=quality_report or {"status": "NOT_RUN"},
        drift_summary={
            "score": (quality_report or {}).get("drift_score"),
            "interpretation": "0 is no measured drift; 100 is maximum bounded deterministic drift.",
        },
        memory_context=memory_context or {},
        notes=[
            "Evidence packs are Git-friendly summaries, not a second backlog or dashboard.",
            "Repository authorities remain canonical; this pack records the decision and evidence around the design work.",
        ],
    )


def write_evidence_pack(pack: EvidencePack, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() == ".json":
        output.write_text(json.dumps(pack.to_dict(), indent=2), encoding="utf-8")
        return
    output.write_text(render_evidence_markdown(pack), encoding="utf-8")


def render_evidence_markdown(pack: EvidencePack) -> str:
    lines = [
        "# Evidence Pack",
        "",
        "## Decision summary",
        pack.decision_summary,
        "",
        "## Design contract",
        f"- task: {pack.contract.get('taskId', 'none')}",
        f"- product: {pack.contract.get('product', 'none')}",
        f"- surface: {pack.contract.get('surface', 'none')}",
        f"- primary action: {pack.contract.get('primaryAction', 'none')}",
        f"- acceptance criteria: {len(pack.contract.get('acceptanceCriteria', []))}",
        "",
        "## Institutional memory context",
        f"- inherited rules: {len(pack.memory_context.get('inherited_rules', []))}",
        f"- relevant decisions: {len(pack.memory_context.get('decisions', []))}",
        f"- active exceptions: {len(pack.memory_context.get('active_exceptions', []))}",
        f"- rejected outcomes: {len(pack.memory_context.get('rejected_outcomes', []))}",
        f"- unresolved debt: {len(pack.memory_context.get('unresolved_debt', []))}",
        f"- bounded retrieval: {pack.memory_context.get('bounded', False)}",
        "",
        "## Before screenshots",
    ]
    lines.extend(f"- {item}" for item in pack.before_screenshots or ["none"])
    lines.extend(["", "## After screenshots"])
    lines.extend(f"- {item}" for item in pack.after_screenshots or ["none"])
    lines.extend(["", "## Lint summary", f"- status: {pack.lint_summary['status']}"])
    for category, count in pack.lint_summary["counts"].items():
        lines.append(f"- {category}: {count}")
    lines.extend(
        [
            "",
            "## Review summary",
            f"- verdict: {pack.review_summary['verdict']}",
            f"- covered viewports: {', '.join(pack.review_summary['covered_viewports']) or 'none'}",
            "",
            "## Quality and drift",
            f"- status: {pack.quality_summary.get('status', 'NOT_RUN')}",
            f"- score: {pack.quality_summary.get('score', 'NOT_RUN')}",
            f"- drift score: {pack.drift_summary.get('score', 'NOT_RUN')}",
            "- scoring boundary: deterministic evidence only; model review is not converted into numeric truth",
            "",
            "## Known debt",
        ]
    )
    lines.extend(f"- {item}" for item in pack.known_debt or ["none"])
    if pack.notes:
        lines.extend(["", "## Notes"])
        lines.extend(f"- {item}" for item in pack.notes)
    return "\n".join(lines)
