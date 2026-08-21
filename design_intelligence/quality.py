from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from .models import QualityReport, ReviewVerdict
from .storage import append_jsonl, atomic_write_json, read_json


def load_thresholds(path: str | Path | None = None) -> dict[str, Any]:
    if path:
        return read_json(path, {}) or {}
    default = files("design_intelligence").joinpath("data/defaults/quality-thresholds.json")
    return json.loads(default.read_text(encoding="utf-8"))


def score_quality(qa_report: dict[str, Any], thresholds: dict[str, Any]) -> QualityReport:
    viewports = qa_report.get("viewports", [])
    totals = qa_report.get("totals", {})
    weights = thresholds["weights"]
    critical = int(totals.get("criticalAccessibilityViolations", 0))
    serious = int(totals.get("seriousAccessibilityViolations", 0))
    moderate = int(totals.get("moderateAccessibilityViolations", 0))
    containment_failures = int(totals.get("containmentFailures", 0))
    dom_passed = int(totals.get("domAssertionsPassed", 0))
    dom_total = int(totals.get("domAssertionsTotal", 0))
    contract_passed = int(totals.get("contractAssertionsPassed", 0))
    contract_total = int(totals.get("contractAssertionsTotal", 0))
    visual_passed = sum(1 for item in viewports if item.get("visual", {}).get("status") == "PASS")
    visual_ratios = [
        float(value)
        for item in viewports
        if isinstance((value := item.get("visual", {}).get("diffRatio")), (int, float))
    ]
    viewport_count = len(viewports)

    accessibility_points = max(0, weights["accessibility"] - critical * 25 - serious * 10 - moderate * 2)
    containment_points = max(0, weights["viewportContainment"] - containment_failures * 10)
    dom_points = _ratio_points(weights["domState"], dom_passed, dom_total)
    visual_points = _ratio_points(weights["visualDrift"], visual_passed, viewport_count)
    contract_points = _ratio_points(weights["contract"], contract_passed, contract_total)
    categories = {
        "accessibility": {"score": accessibility_points, "max": weights["accessibility"], "critical": critical, "serious": serious, "moderate": moderate},
        "viewportContainment": {"score": containment_points, "max": weights["viewportContainment"], "failures": containment_failures},
        "domState": {"score": dom_points, "max": weights["domState"], "passed": dom_passed, "total": dom_total},
        "visualDrift": {
            "score": visual_points,
            "max": weights["visualDrift"],
            "passed": visual_passed,
            "total": viewport_count,
            "measured": len(visual_ratios),
        },
        "contract": {"score": contract_points, "max": weights["contract"], "passed": contract_passed, "total": contract_total},
    }
    score = sum(int(category["score"]) for category in categories.values())
    gates = {
        "criticalAccessibility": critical <= thresholds["maxCriticalAccessibilityViolations"],
        "seriousAccessibility": serious <= thresholds["maxSeriousAccessibilityViolations"],
        "viewportCoverage": viewport_count >= thresholds["requiredViewportCount"],
        "viewportContainment": containment_failures == 0,
        "baselineGovernance": all(item.get("visual", {}).get("governed", False) for item in viewports),
        "visualThreshold": all(item.get("visual", {}).get("status") == "PASS" for item in viewports),
        "contract": contract_total > 0 and contract_passed == contract_total,
        "repairLimit": int(qa_report.get("repairIterations", 0)) <= thresholds["maxRepairIterations"],
    }
    status = ReviewVerdict.PASS if score >= thresholds["qualityPassScore"] and all(gates.values()) else ReviewVerdict.FAIL
    structural_drift = min(100, containment_failures * 25 + (dom_total - dom_passed) * 10)
    visual_drift = max(visual_ratios, default=0.0)
    normalized_visual = min(100, round(visual_drift / max(thresholds["maxPixelDiffRatio"], 0.000001) * 50))
    drift_score = min(100, structural_drift + normalized_visual)
    notes = [
        "The score contains measurable categories only; model visual-review findings are reported separately.",
        "Automated accessibility passing does not replace manual semantic review.",
    ]
    if len(visual_ratios) < viewport_count:
        notes.append(
            "Governed pixel evidence was unavailable for one or more viewports; those viewports receive no visual points and cannot pass baseline gates."
        )
    return QualityReport(
        status=status,
        score=score,
        pass_threshold=thresholds["qualityPassScore"],
        categories=categories,
        mandatory_gates=gates,
        deterministic_only=True,
        drift_score=drift_score,
        notes=notes,
    )


def write_quality_report(
    report: QualityReport,
    latest_path: str | Path,
    history_path: str | Path | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    payload = {**report.to_dict(), "metadata": metadata or {}}
    atomic_write_json(latest_path, payload)
    if history_path:
        append_jsonl(history_path, payload)


def audit_thresholds(thresholds: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if thresholds.get("qualityPassScore", 0) < 90:
        errors.append("qualityPassScore cannot be lower than 90")
    if thresholds.get("maxPixelDiffRatio", 1) > 0.005:
        errors.append("maxPixelDiffRatio cannot be higher than 0.005")
    if thresholds.get("requiredViewportCount", 0) < 5:
        errors.append("requiredViewportCount cannot be lower than 5")
    if thresholds.get("maxRepairIterations", 99) > 3:
        errors.append("maxRepairIterations cannot exceed 3")
    if thresholds.get("maxCriticalAccessibilityViolations", 1) != 0:
        errors.append("Critical accessibility tolerance must remain zero")
    if thresholds.get("maxSeriousAccessibilityViolations", 1) != 0:
        errors.append("Serious accessibility tolerance must remain zero")
    return errors


def _ratio_points(weight: int, passed: int, total: int) -> int:
    if total <= 0:
        return 0
    return round(weight * max(0, min(1, passed / total)))
