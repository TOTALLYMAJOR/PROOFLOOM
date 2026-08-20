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
    PRESERVE = "PRESERVE"
    ALIGN = "ALIGN"
    CONVERGE = "CONVERGE"
    MIGRATE = "MIGRATE"


@dataclass
class CapabilitySignal:
    status: Presence
    evidence: list[str] = field(default_factory=list)
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
    accessibility_tooling: CapabilitySignal
    existing_design_skills: CapabilitySignal
    authorities: dict[str, list[str]]
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
    add: list[str]
    do_not_add: list[str]
    notes: list[str] = field(default_factory=list)

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
