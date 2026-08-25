from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Presence(StrEnum):
    PRESENT = "PRESENT"
    PARTIAL = "PARTIAL"
    NONE = "NONE"


class RepositoryMaturity(StrEnum):
    ESTABLISHED = "ESTABLISHED"
    PARTIAL = "PARTIAL"
    GREENFIELD = "GREENFIELD"


class Recommendation(StrEnum):
    PRESERVE = "PRESERVE"
    INTEGRATE = "INTEGRATE"
    ADD = "ADD"
    MIGRATE = "MIGRATE"


class StructureRisk(StrEnum):
    KEEP = "KEEP"
    ALIGN = "ALIGN"
    CONVERGE = "CONVERGE"
    RESTRUCTURE = "RESTRUCTURE"


class Strategy(StrEnum):
    KEEP = "KEEP"
    PRESERVE = "KEEP"
    ALIGN = "ALIGN"
    CONVERGE = "CONVERGE"
    RESTRUCTURE = "RESTRUCTURE"
    MIGRATE = "RESTRUCTURE"


class Severity(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class BlastRadius(StrEnum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"
    R5 = "R5"


class Confidence(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ReviewVerdict(StrEnum):
    PASS = "PASS"
    NEEDS_WORK = "NEEDS_WORK"
    FAIL = "FAIL"


class LintStatus(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class AuthorityLevel(StrEnum):
    PORTFOLIO = "portfolio"
    ARCHETYPE = "archetype"
    PRODUCT = "product"
    SURFACE = "surface"
    COMPONENT = "component"
    EXCEPTION = "exception"


class DecisionStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    SUPERSEDED = "superseded"
    DEPRECATED = "deprecated"
    REJECTED = "rejected"
    EXPERIMENTAL = "experimental"


class OutcomeResult(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


@dataclass
class CapabilitySignal:
    status: Presence
    evidence: list[str] = field(default_factory=list)
    note: str | None = None


@dataclass
class CapabilityAuthority:
    capability: str
    status: Presence
    authorities: list[str] = field(default_factory=list)
    strategy: Recommendation = Recommendation.ADD
    note: str | None = None


@dataclass
class DuplicateAuthority:
    capability: str
    authorities: list[str]
    severity: Severity
    note: str


@dataclass
class DesignMemoryAuthority:
    authority_paths: list[str] = field(default_factory=list)
    fallback_path: str = "docs/design/decisions"
    strategy: Recommendation = Recommendation.ADD
    note: str | None = None


@dataclass
class RepositorySnapshot:
    root: str
    scanned_paths: list[str]
    ignored_patterns: list[str]
    files_considered: list[str]
    frontend: str
    styling: str
    component_system: str
    repository_maturity: RepositoryMaturity
    design_tokens: CapabilitySignal
    typography: CapabilitySignal
    design_documentation: CapabilitySignal
    agent_governance: CapabilitySignal
    playwright: CapabilitySignal
    cypress: CapabilitySignal
    storybook: CapabilitySignal
    accessibility_tooling: CapabilitySignal
    existing_design_skills: CapabilitySignal
    institutional_design_memory: DesignMemoryAuthority
    capability_map: dict[str, CapabilityAuthority]
    semantic_duplicates: list[DuplicateAuthority] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _normalize(asdict(self))


@dataclass
class MigrationAssessment:
    recommendation: StructureRisk
    knowledge_posture: StructureRisk
    runtime_posture: StructureRisk
    benefit_score: int
    risk_score: int
    confidence: Confidence
    blast_radius: BlastRadius
    benefit_breakdown: dict[str, int]
    risk_breakdown: dict[str, int]
    eighty_twenty_actions: list[str]
    knowledge_migration: list[str]
    runtime_migration: list[str]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _normalize(asdict(self))


@dataclass
class RepositoryAssessment:
    snapshot: RepositorySnapshot
    recommendation: Recommendation
    structure_risk: StructureRisk
    knowledge_strategy: Strategy
    runtime_strategy: Strategy
    preserve: list[str]
    integrate: list[str]
    add: list[str]
    migrate: list[str]
    do_not_add: list[str]
    migration_assessment: MigrationAssessment
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _normalize(asdict(self))


@dataclass
class ProductProfile:
    name: str
    archetype: str
    core_promise: str
    design_psychology: list[str]
    ux_implications: list[str]
    density_modes: list[str]
    dominant_questions: list[str]
    design_emphasis: list[str]
    actor_defaults: dict[str, str]
    requires_institutional_memory: bool = True
    requires_governance_receipt: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _normalize(asdict(self))


@dataclass
class ActorTaskModel:
    actor: str
    object: str
    goal: str
    decision: str
    state: str
    blocker: str
    authority: str
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return _normalize(asdict(self))


@dataclass
class ContextReport:
    profile: ProductProfile | None
    actor_task_model: ActorTaskModel
    repo_posture: StructureRisk
    design_language_focus: list[str]
    validation_focus: list[str]
    reference_use: list[str]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _normalize(asdict(self))


@dataclass
class ReferenceTransformation:
    source: str
    score: int
    keep: list[str]
    adapt: list[str]
    avoid: list[str]
    originality_guardrails: list[str]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _normalize(asdict(self))


@dataclass
class ReferenceReport:
    profile: ProductProfile | None
    transformations: list[ReferenceTransformation]
    overall_clone_risk: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _normalize(asdict(self))


@dataclass
class LintFinding:
    rule_id: str
    category: str
    severity: Severity
    file: str
    line: int
    message: str
    evidence: str
    repairable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _normalize(asdict(self))


@dataclass
class LintReport:
    root: str
    findings: list[LintFinding]
    intentional_exceptions: list[str]
    status: LintStatus
    counts: dict[str, int]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _normalize(asdict(self))


@dataclass
class ReviewFinding:
    surface: str
    viewport: str
    severity: Severity
    root_cause: str
    evidence: str
    preserve: list[str]
    change: list[str]
    repairable: bool
    source: str

    def to_dict(self) -> dict[str, Any]:
        return _normalize(asdict(self))


@dataclass
class ReviewReport:
    surface: str
    verdict: ReviewVerdict
    findings: list[ReviewFinding]
    covered_viewports: list[str]
    remaining_debt: list[str]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _normalize(asdict(self))


@dataclass
class EvidencePack:
    contract: dict[str, Any]
    repo_context: dict[str, Any]
    before_screenshots: list[str]
    after_screenshots: list[str]
    lint_summary: dict[str, Any]
    review_summary: dict[str, Any]
    decision_summary: str
    known_debt: list[str]
    quality_summary: dict[str, Any] = field(default_factory=dict)
    drift_summary: dict[str, Any] = field(default_factory=dict)
    memory_context: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _normalize(asdict(self))


@dataclass
class RepairCandidate:
    rule_id: str
    severity: Severity
    file: str
    line: int
    action: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return _normalize(asdict(self))


@dataclass
class ValidationReport:
    snapshot: RepositorySnapshot
    assessment: RepositoryAssessment
    lint_report: LintReport
    review_report: ReviewReport | None
    status: ReviewVerdict
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _normalize(asdict(self))


@dataclass
class DoctorReport:
    snapshot: RepositorySnapshot
    lint_report: LintReport
    blockers: list[str]
    safe_repairs: list[RepairCandidate]
    bounded_repair_policy: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _normalize(asdict(self))


@dataclass
class MemoryContext:
    product: str | None
    archetype: str | None
    surface: str | None
    component: str | None
    inherited_rules: list[dict[str, Any]]
    decisions: list[dict[str, Any]]
    binding_decisions: list[dict[str, Any]]
    advisory_decisions: list[dict[str, Any]]
    historical_decisions: list[dict[str, Any]]
    active_exceptions: list[dict[str, Any]]
    rejected_outcomes: list[dict[str, Any]]
    unresolved_debt: list[dict[str, Any]]
    stale_records: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    bounded: bool
    total_available: int

    def to_dict(self) -> dict[str, Any]:
        return _normalize(asdict(self))


@dataclass
class QualityReport:
    status: ReviewVerdict
    score: int
    pass_threshold: int
    categories: dict[str, dict[str, Any]]
    mandatory_gates: dict[str, bool]
    deterministic_only: bool
    drift_score: int
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _normalize(asdict(self))


@dataclass
class RepairRun:
    plan_id: str
    status: str
    iteration: int
    max_iterations: int
    changed_files: list[str]
    applied_repairs: list[dict[str, Any]]
    blocked_reasons: list[str]
    before_hashes: dict[str, str]
    after_hashes: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return _normalize(asdict(self))


def _normalize(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    return value
