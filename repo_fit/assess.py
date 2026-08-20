from __future__ import annotations

import argparse
import json
from pathlib import Path

from .inspect import inspect_repository
from .models import (
    Presence,
    Recommendation,
    RepositoryAssessment,
    RepositorySnapshot,
    Strategy,
    StructureRisk,
)


def assess_repository(root: str | Path) -> RepositoryAssessment:
    snapshot = inspect_repository(root)
    structure_risk = _structure_risk(snapshot)
    knowledge_strategy = _knowledge_strategy(snapshot)
    runtime_strategy = Strategy.MIGRATE if structure_risk == StructureRisk.RESTRUCTURE else Strategy.PRESERVE
    recommendation = _recommendation(snapshot, structure_risk)

    preserve = _preserve_list(snapshot)
    add = _add_list(snapshot)
    do_not_add = [
        "second token system",
        "second component library",
        "parallel E2E hierarchy",
        "replacement repository scaffold",
        "automatic runtime restructuring",
    ]

    notes = list(snapshot.notes)
    if runtime_strategy == Strategy.PRESERVE and knowledge_strategy != Strategy.PRESERVE:
        notes.append("Prefer knowledge alignment over runtime migration for this repository.")
    if snapshot.agent_governance.status == Presence.PRESENT:
        notes.append("Existing repository authorities outrank package defaults.")

    return RepositoryAssessment(
        snapshot=snapshot,
        recommendation=recommendation,
        structure_risk=structure_risk,
        knowledge_strategy=knowledge_strategy,
        runtime_strategy=runtime_strategy,
        preserve=preserve,
        add=add,
        do_not_add=do_not_add,
        notes=notes,
    )


def _structure_risk(snapshot: RepositorySnapshot) -> StructureRisk:
    conflict_score = 0
    if len(snapshot.authorities.get("design_docs", [])) >= 2:
        conflict_score += 2
    if snapshot.component_system == "Mixed local primitives":
        conflict_score += 2
    if len(snapshot.authorities.get("component_directories", [])) >= 3:
        conflict_score += 1

    if conflict_score >= 4:
        return StructureRisk.RESTRUCTURE
    if conflict_score >= 2:
        return StructureRisk.CONVERGE
    if snapshot.repository_maturity.value == "ESTABLISHED":
        return StructureRisk.ALIGN
    return StructureRisk.KEEP


def _knowledge_strategy(snapshot: RepositorySnapshot) -> Strategy:
    if len(snapshot.authorities.get("design_docs", [])) >= 2:
        return Strategy.CONVERGE
    if snapshot.design_documentation.status == Presence.NONE and snapshot.frontend != "Unknown":
        return Strategy.ALIGN
    return Strategy.PRESERVE


def _recommendation(snapshot: RepositorySnapshot, structure_risk: StructureRisk) -> Recommendation:
    if snapshot.repository_maturity.value == "GREENFIELD":
        return Recommendation.ADD
    if structure_risk == StructureRisk.RESTRUCTURE:
        return Recommendation.MIGRATE
    return Recommendation.INTEGRATE


def _preserve_list(snapshot: RepositorySnapshot) -> list[str]:
    preserve: list[str] = []
    if snapshot.frontend != "Unknown":
        preserve.append("current runtime scaffold")
    if snapshot.styling != "Unknown":
        preserve.append(f"existing {snapshot.styling} styling system")
    if snapshot.component_system != "Unknown":
        preserve.append(snapshot.component_system)
    if snapshot.typography.status != Presence.NONE:
        preserve.append("typography hierarchy")
    if snapshot.playwright.status != Presence.NONE:
        preserve.append("existing Playwright hierarchy")
    if snapshot.agent_governance.status == Presence.PRESENT:
        preserve.append("existing repository instruction authority")
    return preserve


def _add_list(snapshot: RepositorySnapshot) -> list[str]:
    add: list[str] = []
    if snapshot.existing_design_skills.status == Presence.NONE:
        add.extend(
            [
                "design-language capability",
                "UX reasoning capability",
                "reference-analysis methodology",
                "visual-review rubric",
            ]
        )
    if snapshot.design_documentation.status == Presence.NONE:
        add.append("product design profile")
    return add


def render_assessment_text(assessment: RepositoryAssessment) -> str:
    snapshot = assessment.snapshot
    lines = [
        "DESIGN REPOSITORY ASSESSMENT",
        "",
        "Repository maturity:",
        snapshot.repository_maturity.value,
        "",
        "Frontend:",
        snapshot.frontend,
        "",
        "Styling:",
        snapshot.styling,
        "",
        "Component system:",
        snapshot.component_system,
        "",
        "Design tokens:",
        snapshot.design_tokens.status.value,
        "",
        "Typography:",
        snapshot.typography.status.value,
        "",
        "Design documentation:",
        snapshot.design_documentation.status.value,
        "",
        "Agent governance:",
        snapshot.agent_governance.status.value,
        "",
        "Playwright:",
        snapshot.playwright.status.value,
        "",
        "Accessibility tooling:",
        snapshot.accessibility_tooling.status.value,
        "",
        "Existing design skills:",
        snapshot.existing_design_skills.status.value,
        "",
        "RECOMMENDATION:",
        assessment.recommendation.value,
        "",
        "STRUCTURE RISK:",
        assessment.structure_risk.value,
        "",
        "KNOWLEDGE STRATEGY:",
        assessment.knowledge_strategy.value,
        "",
        "RUNTIME STRATEGY:",
        assessment.runtime_strategy.value,
        "",
        "PRESERVE:",
    ]
    lines.extend(f"- {item}" for item in assessment.preserve)
    lines.extend(["", "ADD:"])
    lines.extend(f"- {item}" for item in assessment.add)
    lines.extend(["", "DO NOT ADD:"])
    lines.extend(f"- {item}" for item in assessment.do_not_add)
    if assessment.notes:
        lines.extend(["", "NOTES:"])
        lines.extend(f"- {item}" for item in assessment.notes)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assess repo-fit for a repository.")
    parser.add_argument("--root", default=".", help="Repository root to inspect.")
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="text",
        help="Output format.",
    )
    args = parser.parse_args(argv)

    assessment = assess_repository(args.root)
    if args.format == "json":
        print(json.dumps(assessment.to_dict(), indent=2))
    else:
        print(render_assessment_text(assessment))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
