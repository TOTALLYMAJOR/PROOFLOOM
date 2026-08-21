from __future__ import annotations

from .models import BlastRadius, Confidence, MigrationAssessment, Presence, RepositorySnapshot, StructureRisk


def assess_migration(snapshot: RepositorySnapshot) -> MigrationAssessment:
    knowledge_posture = _knowledge_posture(snapshot)
    runtime_posture = _runtime_posture(snapshot)
    recommendation = _overall_posture(knowledge_posture, runtime_posture)
    benefit_breakdown = _benefit_breakdown(snapshot)
    risk_breakdown = _risk_breakdown(snapshot, runtime_posture)
    benefit_score = sum(benefit_breakdown.values())
    risk_score = sum(risk_breakdown.values())
    confidence = _confidence(snapshot)
    blast_radius = _blast_radius(runtime_posture, risk_score)
    eighty_twenty = _eighty_twenty_actions(snapshot)
    knowledge_migration = _knowledge_migrations(snapshot)
    runtime_migration = _runtime_migrations(snapshot, runtime_posture)
    notes = _notes(snapshot, knowledge_posture, runtime_posture, benefit_score, risk_score)

    return MigrationAssessment(
        recommendation=recommendation,
        knowledge_posture=knowledge_posture,
        runtime_posture=runtime_posture,
        benefit_score=benefit_score,
        risk_score=risk_score,
        confidence=confidence,
        blast_radius=blast_radius,
        benefit_breakdown=benefit_breakdown,
        risk_breakdown=risk_breakdown,
        eighty_twenty_actions=eighty_twenty,
        knowledge_migration=knowledge_migration,
        runtime_migration=runtime_migration,
        notes=notes,
    )


def _knowledge_posture(snapshot: RepositorySnapshot) -> StructureRisk:
    duplicate_count = len(snapshot.semantic_duplicates)
    if snapshot.design_documentation.status == Presence.NONE and snapshot.frontend != "Unknown":
        return StructureRisk.ALIGN
    if snapshot.institutional_design_memory.authority_paths and duplicate_count == 0:
        return StructureRisk.KEEP
    if duplicate_count >= 2:
        return StructureRisk.CONVERGE
    if snapshot.design_documentation.status == Presence.PARTIAL:
        return StructureRisk.CONVERGE
    return StructureRisk.ALIGN if snapshot.repository_maturity != snapshot.repository_maturity.GREENFIELD else StructureRisk.KEEP


def _runtime_posture(snapshot: RepositorySnapshot) -> StructureRisk:
    if snapshot.component_system == "Competing local UI systems":
        return StructureRisk.CONVERGE
    if snapshot.component_system == "shadcn + competing local primitives":
        return StructureRisk.CONVERGE
    if any(duplicate.capability == "component_system" for duplicate in snapshot.semantic_duplicates):
        return StructureRisk.CONVERGE
    return StructureRisk.KEEP


def _overall_posture(knowledge_posture: StructureRisk, runtime_posture: StructureRisk) -> StructureRisk:
    order = {
        StructureRisk.KEEP: 0,
        StructureRisk.ALIGN: 1,
        StructureRisk.CONVERGE: 2,
        StructureRisk.RESTRUCTURE: 3,
    }
    return knowledge_posture if order[knowledge_posture] >= order[runtime_posture] else runtime_posture


def _benefit_breakdown(snapshot: RepositorySnapshot) -> dict[str, int]:
    return {
        "context_efficiency": 4 if snapshot.agent_governance.status == Presence.NONE else 1,
        "instruction_clarity": 4 if snapshot.agent_governance.status == Presence.NONE else 2,
        "documentation_discoverability": 4 if snapshot.design_documentation.status == Presence.NONE else 2,
        "reduced_drift": min(5, 2 + len(snapshot.semantic_duplicates)),
        "parallel_agent_safety": 4 if len(snapshot.semantic_duplicates) >= 2 else 2,
        "task_resumption": 4 if not snapshot.institutional_design_memory.authority_paths else 2,
        "refactor_safety": 4 if snapshot.design_documentation.status != Presence.PRESENT else 2,
        "knowledge_retention": 4 if not snapshot.institutional_design_memory.authority_paths else 1,
        "token_efficiency": 4 if snapshot.design_tokens.status == Presence.NONE else 2,
        "validation_reliability": 4 if snapshot.playwright.status == Presence.NONE and snapshot.storybook.status == Presence.NONE else 2,
    }


def _risk_breakdown(snapshot: RepositorySnapshot, runtime_posture: StructureRisk) -> dict[str, int]:
    active_test_infra = int(snapshot.playwright.status != Presence.NONE) + int(snapshot.storybook.status != Presence.NONE)
    component_risk = 4 if runtime_posture == StructureRisk.CONVERGE else 1
    return {
        "code_movement_risk": component_risk,
        "import_breakage_risk": component_risk,
        "test_breakage_risk": 2 + active_test_infra,
        "ci_cd_risk": 2 if snapshot.repository_maturity == snapshot.repository_maturity.ESTABLISHED else 1,
        "documentation_loss_risk": 3 if snapshot.institutional_design_memory.authority_paths else 1,
        "dual_system_risk": min(5, 2 + len(snapshot.semantic_duplicates)),
        "developer_confusion_risk": 3 if len(snapshot.semantic_duplicates) >= 2 else 1,
        "agent_confusion_risk": 3 if snapshot.agent_governance.status == Presence.PARTIAL else 1,
        "merge_branch_risk": 3 if snapshot.repository_maturity == snapshot.repository_maturity.ESTABLISHED else 1,
        "rollback_complexity": 3 if runtime_posture == StructureRisk.CONVERGE else 1,
        "generated_code_risk": 1,
        "framework_convention_risk": 2 if snapshot.frontend == "Next.js" else 1,
    }


def _confidence(snapshot: RepositorySnapshot) -> Confidence:
    evidence_count = len(snapshot.files_considered)
    if evidence_count >= 20:
        return Confidence.HIGH
    if evidence_count >= 8:
        return Confidence.MEDIUM
    return Confidence.LOW


def _blast_radius(runtime_posture: StructureRisk, risk_score: int) -> BlastRadius:
    if runtime_posture == StructureRisk.KEEP:
        return BlastRadius.R1 if risk_score >= 18 else BlastRadius.R0
    if runtime_posture == StructureRisk.ALIGN:
        return BlastRadius.R2
    if runtime_posture == StructureRisk.CONVERGE:
        return BlastRadius.R3 if risk_score < 28 else BlastRadius.R4
    return BlastRadius.R5


def _eighty_twenty_actions(snapshot: RepositorySnapshot) -> list[str]:
    actions: list[str] = []
    if snapshot.agent_governance.status == Presence.NONE:
        actions.append("Add one concise repository navigation file before adding deeper design guidance.")
    if snapshot.design_documentation.status == Presence.NONE:
        actions.append("Create one canonical design-language or design-system authority rather than multiple partial notes.")
    if not snapshot.institutional_design_memory.authority_paths:
        actions.append("Add one Git-friendly design decision log only if no existing decision system owns that capability.")
    if snapshot.playwright.status == Presence.NONE and snapshot.storybook.status == Presence.NONE:
        actions.append("Integrate with an existing validation harness first; add a minimal one only if missing and justified.")
    if snapshot.component_system in {"Competing local UI systems", "shadcn + competing local primitives"}:
        actions.append("Converge duplicate primitives through adapters or facades before moving runtime code.")
    return actions or ["Current structure is close to sufficient; prefer incremental alignment over broad migration."]


def _knowledge_migrations(snapshot: RepositorySnapshot) -> list[str]:
    migrations: list[str] = []
    if snapshot.design_documentation.status == Presence.NONE:
        migrations.append("Introduce one canonical design-language authority.")
    if not snapshot.institutional_design_memory.authority_paths:
        migrations.append("Create a lightweight design decision history under docs/design/decisions.")
    if snapshot.agent_governance.status == Presence.NONE:
        migrations.append("Add a concise repository navigation file that points to existing deeper authorities.")
    return migrations


def _runtime_migrations(snapshot: RepositorySnapshot, runtime_posture: StructureRisk) -> list[str]:
    if runtime_posture == StructureRisk.KEEP:
        return ["Runtime restructure is not justified; preserve application boundaries and prefer knowledge alignment."]
    return [
        "Identify canonical UI primitives and add compatibility seams before consolidating duplicates.",
        "Move only high-confidence duplicate components; do not change business behavior under refactoring.",
    ]


def _notes(
    snapshot: RepositorySnapshot,
    knowledge_posture: StructureRisk,
    runtime_posture: StructureRisk,
    benefit_score: int,
    risk_score: int,
) -> list[str]:
    notes = []
    if runtime_posture == StructureRisk.KEEP:
        notes.append("Knowledge-architecture changes capture most of the value here; runtime restructure is not justified.")
    if knowledge_posture == StructureRisk.CONVERGE:
        notes.append("Converge documentation and authority before adding new package-owned guidance.")
    if benefit_score < risk_score:
        notes.append("The benefit/risk split favors 80/20 alignment over broad migration.")
    if snapshot.repository_maturity == snapshot.repository_maturity.GREENFIELD:
        notes.append("Greenfield repos can accept package defaults, but only in the minimum viable shape.")
    return notes


def render_migration_text(report: MigrationAssessment) -> str:
    lines = [
        "REFACTOR RISK ASSESSMENT",
        "",
        f"RECOMMENDATION: {report.recommendation.value}",
        f"KNOWLEDGE POSTURE: {report.knowledge_posture.value}",
        f"RUNTIME POSTURE: {report.runtime_posture.value}",
        f"BENEFIT: {report.benefit_score}/50",
        f"RISK: {report.risk_score}/60",
        f"BLAST RADIUS: {report.blast_radius.value}",
        f"CONFIDENCE: {report.confidence.value}",
        "",
        "80/20 ACTIONS:",
    ]
    lines.extend(f"- {item}" for item in report.eighty_twenty_actions)
    lines.extend(["", "KNOWLEDGE MIGRATION:"])
    lines.extend(f"- {item}" for item in report.knowledge_migration)
    lines.extend(["", "RUNTIME MIGRATION:"])
    lines.extend(f"- {item}" for item in report.runtime_migration)
    if report.notes:
        lines.extend(["", "NOTES:"])
        lines.extend(f"- {item}" for item in report.notes)
    return "\n".join(lines)
