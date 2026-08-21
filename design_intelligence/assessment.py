from __future__ import annotations

from .migrations import assess_migration
from .models import Presence, Recommendation, RepositoryAssessment, RepositorySnapshot, Strategy
from .repository import inspect_repository


def assess_repository(root: str) -> RepositoryAssessment:
    snapshot = inspect_repository(root)
    migration = assess_migration(snapshot)
    recommendation = _recommendation(snapshot, migration.recommendation)
    preserve = _preserve_list(snapshot)
    integrate = _integrate_list(snapshot)
    add = _add_list(snapshot)
    migrate = _migrate_list(snapshot)
    do_not_add = [
        "second token system",
        "second component library",
        "parallel E2E hierarchy",
        "replacement repository scaffold",
        "second decision log when an existing authority already exists",
    ]
    notes = list(snapshot.notes) + list(migration.notes)
    if snapshot.agent_governance.status != Presence.NONE:
        notes.append("Existing repository authorities outrank package defaults.")

    return RepositoryAssessment(
        snapshot=snapshot,
        recommendation=recommendation,
        structure_risk=migration.recommendation,
        knowledge_strategy=Strategy(migration.knowledge_posture.value),
        runtime_strategy=Strategy(migration.runtime_posture.value),
        preserve=preserve,
        integrate=integrate,
        add=add,
        migrate=migrate,
        do_not_add=do_not_add,
        migration_assessment=migration,
        notes=notes,
    )


def _recommendation(snapshot: RepositorySnapshot, posture) -> Recommendation:
    if snapshot.repository_maturity == snapshot.repository_maturity.GREENFIELD:
        return Recommendation.ADD
    if posture == posture.RESTRUCTURE:
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
    if snapshot.storybook.status != Presence.NONE:
        preserve.append("existing Storybook hierarchy")
    if snapshot.agent_governance.status != Presence.NONE:
        preserve.append("existing repository instruction authority")
    if snapshot.institutional_design_memory.authority_paths:
        preserve.append("existing design decision memory")
    return preserve


def _integrate_list(snapshot: RepositorySnapshot) -> list[str]:
    integrate = []
    for capability, item in snapshot.capability_map.items():
        if item.strategy == Recommendation.INTEGRATE:
            integrate.append(capability.replace("_", " "))
    return integrate


def _add_list(snapshot: RepositorySnapshot) -> list[str]:
    add: list[str] = []
    if snapshot.existing_design_skills.status == Presence.NONE:
        add.extend(
            [
                "design-language capability",
                "UX reasoning capability",
                "reference-analysis methodology",
                "visual-review rubric",
                "design-linter capability",
            ]
        )
    if snapshot.design_documentation.status == Presence.NONE:
        add.append("canonical design-language authority")
    if not snapshot.institutional_design_memory.authority_paths:
        add.append("lightweight design decision store")
    return add


def _migrate_list(snapshot: RepositorySnapshot) -> list[str]:
    return [duplicate.capability.replace("_", " ") for duplicate in snapshot.semantic_duplicates]


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
        "Storybook:",
        snapshot.storybook.status.value,
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
    lines.extend(["", "INTEGRATE:"])
    lines.extend(f"- {item}" for item in assessment.integrate)
    lines.extend(["", "ADD:"])
    lines.extend(f"- {item}" for item in assessment.add)
    lines.extend(["", "MIGRATE:"])
    lines.extend(f"- {item}" for item in assessment.migrate or ["none"])
    lines.extend(["", "DO NOT ADD:"])
    lines.extend(f"- {item}" for item in assessment.do_not_add)
    if assessment.notes:
        lines.extend(["", "NOTES:"])
        lines.extend(f"- {item}" for item in assessment.notes)
    return "\n".join(lines)
