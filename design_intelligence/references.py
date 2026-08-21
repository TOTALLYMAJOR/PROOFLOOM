from __future__ import annotations

from typing import Any

from .models import ReferenceReport, ReferenceTransformation
from .profiles import load_profile

CLONE_WORDS = ("copy", "clone", "same palette", "same layout", "match exactly")


def analyze_references(
    references: list[dict[str, Any]], profile_name: str | None = None
) -> ReferenceReport:
    profile = load_profile(profile_name) if profile_name else None
    transformations = [_transform(reference, profile) for reference in references]
    risky = sum(1 for item in transformations if item.score < 5)
    overall_clone_risk = "HIGH" if risky >= max(1, len(transformations) // 2) else "LOW"
    notes = [
        "Reference analysis transfers principles, not identity.",
        "Repository and product truth outrank admired references.",
    ]
    return ReferenceReport(
        profile=profile,
        transformations=transformations,
        overall_clone_risk=overall_clone_risk,
        notes=notes,
    )


def _transform(reference: dict[str, Any], profile) -> ReferenceTransformation:
    source = reference["source"]
    patterns = reference.get("observed_patterns", [])
    strengths = reference.get("strengths", [])
    risks = reference.get("risks", [])
    score = 8
    if any(word in " ".join(patterns).lower() for word in CLONE_WORDS):
        score -= 4
    if any(word in " ".join(risks).lower() for word in CLONE_WORDS):
        score -= 2
    if profile:
        score += 1
    keep = [f"Keep the principle of {item.lower()}." for item in strengths[:3]]
    adapt = [
        _adapt_pattern(pattern, profile)
        for pattern in patterns[:3]
    ] or ["Transform the reference into product-specific hierarchy rather than copying its visual identity."]
    avoid = risks[:3] or ["Avoid importing brand-specific signatures, copy, or ornamental patterns without product evidence."]
    guardrails = [
        "Do not reuse the source brand palette, trademark geometry, or copy.",
        "Tie each adapted pattern to the product's actor, state, and dominant decision.",
    ]
    if profile:
        guardrails.append(f"Ensure the transformation strengthens {profile.core_promise}.")
    notes = ["Direct visual mimicry is not allowed."]
    return ReferenceTransformation(
        source=source,
        score=max(0, min(10, score)),
        keep=keep,
        adapt=adapt,
        avoid=avoid,
        originality_guardrails=guardrails,
        notes=notes,
    )


def _adapt_pattern(pattern: str, profile) -> str:
    base = pattern.strip().rstrip(".")
    if profile:
        return (
            f"Adapt '{base}' to support {profile.core_promise.lower()} with "
            f"{profile.design_psychology[0].lower()} hierarchy rather than copying the source composition."
        )
    return f"Adapt '{base}' to the target product's own hierarchy, states, and task model."


def render_reference_text(report: ReferenceReport) -> str:
    lines = ["REFERENCE INTELLIGENCE", ""]
    if report.profile:
        lines.append(f"Profile: {report.profile.name}")
        lines.append("")
    lines.append(f"Overall clone risk: {report.overall_clone_risk}")
    for item in report.transformations:
        lines.extend(["", f"Source: {item.source}", f"Score: {item.score}/10", "Keep:"])
        lines.extend(f"- {entry}" for entry in item.keep)
        lines.extend(["Adapt:"])
        lines.extend(f"- {entry}" for entry in item.adapt)
        lines.extend(["Avoid:"])
        lines.extend(f"- {entry}" for entry in item.avoid)
        lines.extend(["Guardrails:"])
        lines.extend(f"- {entry}" for entry in item.originality_guardrails)
    if report.notes:
        lines.extend(["", "Notes:"])
        lines.extend(f"- {item}" for item in report.notes)
    return "\n".join(lines)
