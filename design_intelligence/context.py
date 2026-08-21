from __future__ import annotations

from typing import Any

from .assessment import assess_repository
from .models import ActorTaskModel, ContextReport
from .profiles import load_profile


def build_context(root: str, profile_name: str | None = None, brief: dict[str, Any] | None = None) -> ContextReport:
    assessment = assess_repository(root)
    profile = load_profile(profile_name) if profile_name else None
    actor_task_model = _actor_task_model(profile, brief or {})
    design_language_focus = _design_language_focus(profile, assessment.snapshot.component_system)
    validation_focus = _validation_focus(profile)
    reference_use = _reference_use(profile)
    notes = _notes(profile, assessment)
    return ContextReport(
        profile=profile,
        actor_task_model=actor_task_model,
        repo_posture=assessment.structure_risk,
        design_language_focus=design_language_focus,
        validation_focus=validation_focus,
        reference_use=reference_use,
        notes=notes,
    )


def _actor_task_model(profile, brief: dict[str, Any]) -> ActorTaskModel:
    defaults = profile.actor_defaults if profile else {}
    return ActorTaskModel(
        actor=brief.get("actor", defaults.get("actor", "Primary operator")),
        object=brief.get("object", defaults.get("object", "Current surface")),
        goal=brief.get("goal", defaults.get("goal", "Complete the primary task confidently")),
        decision=brief.get("decision", defaults.get("decision", "Choose the next best action")),
        state=brief.get("state", defaults.get("state", "Current state is partially known")),
        blocker=brief.get("blocker", defaults.get("blocker", "Ambiguity around what matters now")),
        authority=brief.get("authority", defaults.get("authority", "Existing repository and product truth")),
        next_action=brief.get("next_action", defaults.get("next_action", "Make the dominant next action explicit")),
    )


def _design_language_focus(profile, component_system: str) -> list[str]:
    focus = []
    if profile:
        focus.extend(profile.design_emphasis)
    if component_system in {"Competing local UI systems", "shadcn + competing local primitives"}:
        focus.append("Preserve visual language while converging duplicate primitives behind compatibility seams.")
    return focus or [
        "Preserve the existing visual language before introducing new tokens or primitives.",
        "Map product personality to visible consequences rather than adjectives.",
    ]


def _validation_focus(profile) -> list[str]:
    if not profile:
        return [
            "Validate desktop and mobile intentionally.",
            "Classify failures by hierarchy, workflow, responsive, accessibility, or drift before changing visuals.",
        ]
    if profile.name == "QuotePilot":
        return [
            "Validate numeric clarity and progression from build to decision to booking.",
            "Ensure primary commercial actions dominate over decorative chrome.",
        ]
    if profile.name == "QuietPilot":
        return [
            "Validate state, blockers, dependencies, and readiness are visible before secondary modules.",
            "Confirm controlled density still keeps next action obvious.",
        ]
    return [
        "Validate mobile glanceability and one-handed comprehension first.",
        "Confirm role-specific disclosure prevents coach/admin complexity from leaking into parent views.",
    ]


def _reference_use(profile) -> list[str]:
    if not profile:
        return ["Use references only to transfer principles; repository truth outranks them."]
    return [
        f"References must be transformed to reinforce {profile.core_promise}, not copied.",
        "Reject admired patterns that erase product-specific differentiation.",
    ]


def _notes(profile, assessment) -> list[str]:
    notes = [
        "Actor/object/goal/decision/state/blocker/authority/next-action reasoning should precede visual polish.",
    ]
    if profile:
        notes.append(f"Profile '{profile.name}' changes what should dominate the interface.")
    if assessment.runtime_strategy.value == "KEEP":
        notes.append("Repository structure does not justify runtime migration for context work.")
    return notes


def render_context_text(report: ContextReport) -> str:
    lines = ["DESIGN CONTEXT", ""]
    if report.profile:
        lines.extend(
            [
                f"Profile: {report.profile.name}",
                f"Archetype: {report.profile.archetype}",
                f"Core promise: {report.profile.core_promise}",
                "",
            ]
        )
    lines.extend(
        [
            f"Repo posture: {report.repo_posture.value}",
            "",
            "Actor-task model:",
            f"- actor: {report.actor_task_model.actor}",
            f"- object: {report.actor_task_model.object}",
            f"- goal: {report.actor_task_model.goal}",
            f"- decision: {report.actor_task_model.decision}",
            f"- state: {report.actor_task_model.state}",
            f"- blocker: {report.actor_task_model.blocker}",
            f"- authority: {report.actor_task_model.authority}",
            f"- next action: {report.actor_task_model.next_action}",
            "",
            "Design language focus:",
        ]
    )
    lines.extend(f"- {item}" for item in report.design_language_focus)
    lines.extend(["", "Validation focus:"])
    lines.extend(f"- {item}" for item in report.validation_focus)
    lines.extend(["", "Reference use:"])
    lines.extend(f"- {item}" for item in report.reference_use)
    if report.notes:
        lines.extend(["", "Notes:"])
        lines.extend(f"- {item}" for item in report.notes)
    return "\n".join(lines)
