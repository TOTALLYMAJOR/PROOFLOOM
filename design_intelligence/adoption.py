from __future__ import annotations

import hashlib
import json
import re
import struct
from datetime import datetime
from pathlib import Path
from typing import Any

from .contracts import create_contract
from .memory import audit_memory, retrieve_context
from .profiles import load_profile
from .repository import inspect_repository
from .review_lifecycle import audit_baseline_review_receipt
from .storage import atomic_write_json, ensure_within, read_json, sha256_file
from .workflows import build_workflow


AUTHORITY_KINDS = (
    ("agent_governance", "agent-governance", "repository-governance", "instructional"),
    ("custom_instructions", "custom-instructions", "agent-behavior", "instructional"),
    ("hooks", "hook", "enforced-process", "automated"),
    ("backlog", "backlog", "product-intent", "documented"),
    ("specifications", "requirement", "product-intent", "documented"),
    ("architecture_overview", "architecture", "architecture", "documented"),
    ("architecture_decisions", "architecture-decision", "architecture", "documented"),
    ("design_decisions", "design-decision", "design-intent", "documented"),
    ("design_language", "design-authority", "design-intent", "documented"),
    ("design_principles", "design-principles", "design-intent", "documented"),
    ("design_contracts", "design-contract", "design-intent", "documented"),
)

PROTECTED_RISK_FLAGS = {
    "accessibility-regression",
    "false-authoritative-state",
    "payment-truth",
    "security-risk",
    "tenant-isolation",
    "workflow-harm",
}

ANALYZER_TYPES = {"human", "model", "hybrid"}
PATTERN_CATEGORIES = {
    "accessibility",
    "component",
    "content",
    "conversion",
    "feature",
    "interaction",
    "layout",
    "mobile",
    "motion",
    "navigation",
    "responsive",
    "typography",
    "visual",
    "workflow",
}
IMPLEMENTATION_IMPACTS = {"visual-only", "component", "workflow", "backend", "architecture"}
PATTERN_LIST_FIELDS = ("keywords", "requiredCapabilities", "riskFlags", "identityElements")


def evaluate_adoption(
    repository_root: str | Path,
    task: str,
    *,
    references: list[str] | None = None,
    images: list[str | Path] | None = None,
    analysis: dict[str, Any] | None = None,
    profile_name: str | None = None,
    surface: str | None = None,
    governance_receipts: list[str | Path | dict[str, Any]] | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    profile = load_profile(profile_name) if profile_name else None
    authorities = discover_adoption_authorities(root)
    design_system = audit_design_system_health(root)
    memory_required = bool(profile and profile.requires_institutional_memory)
    memory_context = _retrieve_memory_context(root, profile_name, surface)
    governance = _evaluate_governance_constraints(
        root,
        governance_receipts or [],
        required=bool(profile and profile.requires_governance_receipt),
    )
    sources = _build_sources(root, references or [], images or [], analysis)
    research_required = bool(sources) and any(
        source["status"] != "ANALYZED" for source in sources
    )
    errors = [
        error
        for source in sources
        for error in source.get("integrityErrors", [])
    ]
    errors.extend(
        f"institutional memory conflict: {json.dumps(conflict, sort_keys=True)}"
        for conflict in memory_context.get("conflicts", [])
    )
    errors.extend(
        f"institutional memory integrity: {error}"
        for error in memory_context.get("audit", {}).get("errors", [])
    )
    errors.extend(governance.get("errors", []))
    capability_claims: dict[str, dict[str, Any]] = {}
    if analysis is not None:
        errors.extend(_validate_analysis(analysis, sources))
        capability_claims = _normalize_capability_claims(
            root,
            analysis.get("capabilityClaims", []),
        )
    decisions = []
    if analysis is not None and not errors and not research_required:
        decisions = [
            _decide_pattern(
                pattern,
                capability_claims,
                authorities["sources"],
                design_system,
                memory_context,
            )
            for pattern in analysis.get("patterns", [])
        ]
    if errors:
        status = "BLOCKED"
    elif governance["status"] == "BLOCKED":
        status = "BLOCKED"
    elif research_required:
        status = "RESEARCH_REQUIRED"
    elif governance["status"] in {"HELD", "REQUIRED"}:
        status = "REVIEW_REQUIRED"
    elif memory_required and memory_context["status"] != "AVAILABLE":
        status = "REVIEW_REQUIRED"
    elif decisions and all(item["decision"] == "DECLINE" for item in decisions):
        status = "DECLINED"
    elif any(item["decision"] == "BLOCKED" for item in decisions):
        status = "BLOCKED"
    elif any(item["decision"] == "DEFER" for item in decisions):
        status = "REVIEW_REQUIRED"
    elif decisions:
        status = "READY"
    else:
        status = "REVIEW_REQUIRED"
    design_contract = (
        _build_adoption_contract(
            root,
            task,
            decisions,
            profile_name,
            surface,
        )
        if status == "READY"
        else None
    )
    report = {
        "schemaVersion": 1,
        "task": task,
        "profile": profile_name,
        "surface": surface,
        "repositoryRoot": str(root),
        "status": status,
        "implementationReady": status == "READY",
        "sources": sources,
        "authorities": authorities,
        "designSystemHealth": design_system,
        "memoryRequired": memory_required,
        "memoryContext": memory_context,
        "governanceConstraints": governance,
        "analysis": analysis,
        "capabilityClaims": list(capability_claims.values()),
        "decisions": decisions,
        "designContract": design_contract,
        "errors": errors,
        "implementationPerformed": False,
        "repairPerformed": False,
        "baselineMutationPerformed": False,
    }
    report["id"] = _report_id(report)
    return report


def discover_adoption_authorities(repository_root: str | Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    snapshot = inspect_repository(root)
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for capability, kind, authority_class, enforcement in AUTHORITY_KINDS:
        item = snapshot.capability_map.get(capability)
        if not item:
            continue
        for relative in item.authorities:
            if relative in seen:
                continue
            path = root / relative
            if not path.is_file():
                continue
            seen.add(relative)
            sources.append({
                "id": _authority_id(kind, relative),
                "kind": kind,
                "authorityClass": authority_class,
                "enforcement": enforcement,
                "path": relative,
                "sha256": sha256_file(path),
                "statements": _extract_statements(path, kind),
            })
    return {
        "status": "PASS",
        "root": str(root),
        "sources": sorted(sources, key=lambda item: (item["kind"], item["path"])),
        "duplicateAuthorities": snapshot.to_dict()["semantic_duplicates"],
    }


def audit_design_system_health(repository_root: str | Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    snapshot = inspect_repository(root)
    snapshot_data = snapshot.to_dict()
    conflicts = [
        item["capability"]
        for item in snapshot_data["semantic_duplicates"]
        if item["capability"] in {"design_language", "component_system"}
    ]
    findings: list[dict[str, str]] = []
    required_actions: list[str] = []
    score = 100

    for item in snapshot_data["semantic_duplicates"]:
        if item["capability"] in {"design_language", "component_system"}:
            score -= 30
            findings.append({
                "severity": item["severity"],
                "category": item["capability"],
                "message": item["note"],
            })
    if conflicts:
        required_actions.append(
            "Converge competing design-language and component authorities before extending the system."
        )
    if snapshot.design_tokens.status.value == "NONE":
        score -= 15
        findings.append({
            "severity": "P2",
            "category": "tokens",
            "message": "No reusable design-token evidence was detected.",
        })
        required_actions.append("Define or identify one canonical token authority before adding new visual roles.")
    if snapshot.component_system == "Unknown":
        score -= 15
        findings.append({
            "severity": "P2",
            "category": "components",
            "message": "No established component system was detected.",
        })
    if snapshot.design_documentation.status.value == "NONE":
        score -= 10
        findings.append({
            "severity": "P3",
            "category": "documentation",
            "message": "No canonical design-language documentation was detected.",
        })
    if snapshot.frontend != "Unknown" and snapshot.accessibility_tooling.status.value == "NONE":
        score -= 10
        findings.append({
            "severity": "P2",
            "category": "accessibility",
            "message": "Frontend code exists without detected accessibility validation.",
        })
        required_actions.append("Establish accessibility evidence before broad design-system adoption.")

    score = max(0, score)
    if conflicts:
        status = "CONFLICTED"
    elif score < 80:
        status = "NEEDS_ALIGNMENT"
    elif snapshot.frontend == "Unknown":
        status = "INSUFFICIENT_EVIDENCE"
    else:
        status = "HEALTHY"
    return {
        "status": status,
        "score": score,
        "safeToExtend": status == "HEALTHY",
        "conflicts": sorted(set(conflicts)),
        "findings": findings,
        "requiredActions": required_actions,
        "evidence": {
            "frontend": snapshot.frontend,
            "styling": snapshot.styling,
            "componentSystem": snapshot.component_system,
            "designTokens": snapshot_data["design_tokens"],
            "designDocumentation": snapshot_data["design_documentation"],
            "accessibilityTooling": snapshot_data["accessibility_tooling"],
        },
    }


def save_adoption_bundle(
    report: dict[str, Any],
    output_root: str | Path,
) -> dict[str, str]:
    root = Path(report["repositoryRoot"]).resolve()
    destination = ensure_within(root, output_root)
    report_path = destination / "adoption-report.json"
    if report_path.exists():
        relative = report_path.relative_to(root).as_posix()
        raise ValueError(f"Adoption reports are append-only: {relative} already exists")
    destination.mkdir(parents=True, exist_ok=True)
    authority_path = destination / "authority-map.json"
    health_path = destination / "design-system-health.json"
    atomic_write_json(authority_path, report["authorities"])
    atomic_write_json(health_path, report["designSystemHealth"])
    outputs = {
        "directory": str(destination),
        "report": str(report_path),
        "authorityMap": str(authority_path),
        "designSystemHealth": str(health_path),
    }
    if report.get("analysis"):
        analysis_path = destination / "reference-analysis.json"
        atomic_write_json(analysis_path, report["analysis"])
        outputs["analysis"] = str(analysis_path)
    else:
        request_path = destination / "analysis-request.json"
        atomic_write_json(request_path, _analysis_request(report))
        outputs["analysisRequest"] = str(request_path)
    if report.get("designContract"):
        contract_path = destination / "design-contract.json"
        atomic_write_json(contract_path, report["designContract"])
        outputs["contract"] = str(contract_path)
    atomic_write_json(report_path, report)
    return outputs


def default_adoption_bundle_path(
    repository_root: str | Path,
    task: str,
) -> Path:
    slug = re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", task.lower()))
    return Path(repository_root).resolve() / "artifacts/design/adoptions" / (slug or "design-adoption")


def render_adoption_text(report: dict[str, Any]) -> str:
    lines = [
        "DESIGN ADOPTION GATE",
        "",
        f"Status: {report['status']}",
        f"Implementation ready: {'YES' if report['implementationReady'] else 'NO'}",
        f"Design-system health: {report['designSystemHealth']['status']}",
        f"Institutional memory: {report['memoryContext']['status']} ({'required' if report['memoryRequired'] else 'optional'})",
        f"Governance constraints: {report['governanceConstraints']['status']}",
        "",
        "Decisions:",
    ]
    if report["decisions"]:
        for item in report["decisions"]:
            lines.append(f"- {item['patternId']}: {item['decision']} - {'; '.join(item['reasons'])}")
    else:
        lines.append("- No pattern decision is authorized until reference research is complete.")
    return "\n".join(lines)


def audit_adoption_report(
    repository_root: str | Path,
    report_path: str | Path,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    source = ensure_within(root, report_path)
    loaded = read_json(source, {})
    report = {} if loaded is None else loaded
    errors = _validate_adoption_report_shape(report)
    if not isinstance(report, dict):
        return {
            "status": "FAIL",
            "reportId": None,
            "checkedSources": 0,
            "checkedAuthorities": 0,
            "errors": errors,
            "warnings": [],
            "checkoutRelocated": False,
        }
    report_sources = report.get("sources") if isinstance(report.get("sources"), list) else []
    report_authorities = report.get("authorities") if isinstance(report.get("authorities"), dict) else {}
    recorded_root = Path(str(report.get("repositoryRoot", ""))).resolve()
    checkout_relocated = recorded_root != root
    warnings = (
        [
            "adoption report originated in a different checkout; "
            "relative source and authority hashes were replay-audited against the current root"
        ]
        if checkout_relocated
        else []
    )
    if report.get("id") != _report_id(report):
        errors.append("adoption report id does not match its evidence identity")
    if not errors:
        for item in report_sources:
            for evidence in item.get("evidence", []):
                _audit_hash_binding(root, f"source {item.get('id')}", evidence, errors)
        for item in report_authorities.get("sources", []):
            _audit_hash_binding(
                root,
                f"authority {item.get('id')}",
                {"path": item.get("path"), "sha256": item.get("sha256")},
                errors,
            )
    if not errors:
        replay = evaluate_adoption(
            root,
            str(report.get("task", "")),
            references=[
                item["location"]
                for item in report_sources
                if item.get("kind") == "url"
            ],
            images=[
                item["location"]
                for item in report_sources
                if item.get("kind") == "image"
            ],
            analysis=report.get("analysis"),
            profile_name=report.get("profile"),
            surface=report.get("surface"),
            governance_receipts=(report.get("governanceConstraints") or {}).get("receipts", []),
        )
        for field in (
            "status", "implementationReady", "memoryRequired", "governanceConstraints",
            "decisions", "designContract",
        ):
            if replay.get(field) != report.get(field):
                errors.append(f"adoption report replay mismatch: {field}")
    return {
        "status": "PASS" if not errors else "FAIL",
        "reportId": report.get("id"),
        "checkedSources": len(report_sources),
        "checkedAuthorities": len(report_authorities.get("sources", [])),
        "errors": errors,
        "warnings": warnings,
        "checkoutRelocated": checkout_relocated,
        "recordedRepositoryRoot": str(recorded_root),
    }


def _validate_adoption_report_shape(report: Any) -> list[str]:
    if not isinstance(report, dict):
        return ["adoption report must be an object"]
    required = (
        "schemaVersion", "id", "task", "profile", "surface", "repositoryRoot", "status",
        "implementationReady", "sources", "authorities", "designSystemHealth",
        "memoryRequired", "memoryContext", "governanceConstraints", "analysis",
        "capabilityClaims", "decisions",
        "designContract", "errors", "implementationPerformed", "repairPerformed",
        "baselineMutationPerformed",
    )
    errors = [f"adoption report missing field: {field}" for field in required if field not in report]
    if report.get("schemaVersion") != 1:
        errors.append("adoption report schemaVersion must be 1")
    if report.get("status") not in {
        "RESEARCH_REQUIRED", "REVIEW_REQUIRED", "READY", "DECLINED", "BLOCKED",
    }:
        errors.append("adoption report status is invalid")
    if not isinstance(report.get("implementationReady"), bool):
        errors.append("adoption report implementationReady must be a boolean")
    elif report.get("implementationReady") != (report.get("status") == "READY"):
        errors.append("adoption report implementationReady does not match status")
    if not isinstance(report.get("memoryRequired"), bool):
        errors.append("adoption report memoryRequired must be a boolean")
    elif report.get("memoryRequired") != (report.get("profile") is not None):
        errors.append("adoption report memoryRequired does not match product-profile policy")
    for field in ("implementationPerformed", "repairPerformed", "baselineMutationPerformed"):
        if report.get(field) is not False:
            errors.append(f"adoption report {field} must be false")
    for field in ("sources", "capabilityClaims", "decisions", "errors"):
        if field in report and not isinstance(report.get(field), list):
            errors.append(f"adoption report {field} must be an array")
    for field in ("authorities", "designSystemHealth", "memoryContext", "governanceConstraints"):
        if field in report and not isinstance(report.get(field), dict):
            errors.append(f"adoption report {field} must be an object")
    return errors


def _evaluate_governance_constraints(
    repository_root: Path,
    receipt_inputs: list[str | Path | dict[str, Any]],
    *,
    required: bool = False,
) -> dict[str, Any]:
    if not receipt_inputs:
        return {
            "status": "REQUIRED" if required else "NOT_REQUIRED",
            "required": required,
            "receipts": [],
            "errors": [],
        }

    receipts: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, value in enumerate(receipt_inputs):
        try:
            authority_root, receipt_path = _resolve_governance_receipt(repository_root, value)
        except ValueError as error:
            errors.append(f"governance receipt {index + 1}: {error}")
            continue
        audit = audit_baseline_review_receipt(authority_root, receipt_path)
        receipt = read_json(receipt_path, {}) or {}
        entry = {
            "authorityRoot": str(authority_root),
            "path": receipt_path.relative_to(authority_root).as_posix(),
            "sha256": sha256_file(receipt_path),
            "receiptId": receipt.get("id"),
            "decision": audit.get("decision"),
            "lifecycle": audit.get("lifecycle"),
            "auditStatus": audit.get("status"),
            "auditErrors": audit.get("errors", []),
        }
        receipts.append(entry)
        if audit.get("status") != "PASS":
            errors.extend(
                f"governance receipt {entry['receiptId'] or index + 1}: {item}"
                for item in audit.get("errors", [])
            )

    decisions = {item.get("decision") for item in receipts}
    inactive_approvals = [
        item for item in receipts
        if item.get("decision") == "APPROVE" and item.get("lifecycle") != "ACTIVE"
    ]
    if errors or not receipts or "REJECT" in decisions or inactive_approvals:
        status = "BLOCKED"
    elif "DEFER" in decisions:
        status = "HELD"
    elif decisions == {"APPROVE"}:
        status = "PASS"
    else:
        status = "BLOCKED"
        errors.append("governance receipts do not establish an active human decision")
    return {
        "status": status,
        "required": required,
        "receipts": receipts,
        "errors": errors,
    }


def _resolve_governance_receipt(
    repository_root: Path,
    value: str | Path | dict[str, Any],
) -> tuple[Path, Path]:
    if isinstance(value, dict):
        authority_value = value.get("authorityRoot")
        path_value = value.get("path")
        if not authority_value or not path_value:
            raise ValueError("authorityRoot and path are required")
        authority_root = Path(str(authority_value)).resolve()
        receipt_path = ensure_within(authority_root, str(path_value))
    else:
        candidate = Path(value)
        receipt_path = candidate.resolve() if candidate.is_absolute() else (repository_root / candidate).resolve()
        authority_root = _find_governance_root(receipt_path)
    if not receipt_path.is_file():
        raise ValueError(f"receipt not found: {receipt_path}")
    return authority_root, receipt_path


def _find_governance_root(receipt_path: Path) -> Path:
    for parent in receipt_path.parents:
        if (parent / ".design/baselines/review-policy.json").is_file():
            return parent
    raise ValueError(f"no governed review-policy root contains {receipt_path}")


def _unresearched_source(kind: str, location: str) -> dict[str, Any]:
    digest = hashlib.sha256(f"{kind}:{location}".encode("utf-8")).hexdigest()[:12].upper()
    return {
        "id": f"SRC-{digest}",
        "kind": kind,
        "location": location,
        "status": "RESEARCH_REQUIRED",
        "evidence": [],
    }


def _build_sources(
    root: Path,
    references: list[str],
    images: list[str | Path],
    analysis: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    analyzed_locations = {
        str(item.get("source"))
        for item in (analysis or {}).get("patterns", [])
        if item.get("source")
    }
    source_evidence = {
        str(item.get("source")): item
        for item in (analysis or {}).get("sourceEvidence", [])
        if item.get("source")
    }
    sources = []
    for reference in references:
        source = _unresearched_source("url", reference)
        if reference in analyzed_locations:
            binding = source_evidence.get(reference)
            if binding:
                evidence, errors = _bind_source_evidence(root, binding)
                source["evidence"] = evidence
                source["integrityErrors"] = errors
                if evidence and not errors:
                    source["status"] = "ANALYZED"
        sources.append(source)
    for image_value in images:
        image = ensure_within(root, image_value)
        if not image.is_file():
            raise ValueError(f"Reference image not found: {image_value}")
        relative = image.relative_to(root).as_posix()
        source = _unresearched_source("image", relative)
        source.update({
            "sha256": sha256_file(image),
            "dimensions": _image_dimensions(image),
            "evidence": [{"path": relative, "sha256": sha256_file(image)}],
        })
        sources.append(source)
    for source in sources:
        if source["kind"] == "image" and source["location"] in analyzed_locations:
            source["status"] = "ANALYZED"
    return sources


def _bind_source_evidence(
    root: Path,
    binding: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    evidence: list[dict[str, Any]] = []
    errors: list[str] = []
    artifacts = binding.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return [], [f"{binding.get('source')}: captured source evidence is required"]
    for artifact in artifacts:
        path_value = artifact.get("path")
        expected = artifact.get("sha256")
        if not path_value or not expected:
            errors.append(f"{binding.get('source')}: evidence path and sha256 are required")
            continue
        try:
            path = ensure_within(root, path_value)
        except ValueError as error:
            errors.append(f"{binding.get('source')}: {error}")
            continue
        if not path.is_file():
            errors.append(f"{binding.get('source')}: evidence file missing: {path_value}")
            continue
        actual = sha256_file(path)
        if actual != expected:
            errors.append(f"{binding.get('source')}: evidence hash mismatch: {path_value}")
            continue
        evidence.append({
            "kind": artifact.get("kind", "capture"),
            "path": path.relative_to(root).as_posix(),
            "sha256": actual,
        })
    return evidence, errors


def _validate_analysis(
    analysis: dict[str, Any],
    sources: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    if analysis.get("schemaVersion") != 1:
        errors.append("analysis.schemaVersion must be 1")
    analyzer = analysis.get("analyzer") or {}
    for field in ("type", "name", "observedAt"):
        if not analyzer.get(field):
            errors.append(f"analysis.analyzer.{field} is required")
    if analyzer.get("type") and analyzer.get("type") not in ANALYZER_TYPES:
        errors.append("analysis.analyzer.type must be human, model, or hybrid")
    observed_at = analyzer.get("observedAt")
    if observed_at:
        try:
            parsed = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                errors.append("analysis.analyzer.observedAt must include a timezone")
        except ValueError:
            errors.append("analysis.analyzer.observedAt must be an ISO-8601 datetime")
    capability_claims = analysis.get("capabilityClaims")
    if not isinstance(capability_claims, list):
        errors.append("analysis.capabilityClaims must be an array")
    else:
        seen_capabilities: set[str] = set()
        for claim in capability_claims:
            if not isinstance(claim, dict):
                errors.append("analysis.capabilityClaims entries must be objects")
                continue
            capability = str(claim.get("capability", ""))
            if not capability:
                errors.append("analysis.capabilityClaims.capability is required")
            elif capability in seen_capabilities:
                errors.append(f"duplicate capability claim: {capability}")
            else:
                seen_capabilities.add(capability)
            if claim.get("status") not in {"VERIFIED", "ABSENT", "UNRESOLVED"}:
                errors.append(f"{capability or '<unknown>'}.status is invalid")
            if not isinstance(claim.get("evidence"), list):
                errors.append(f"{capability or '<unknown>'}.evidence must be an array")
    source_locations = {item["location"] for item in sources}
    patterns = analysis.get("patterns")
    if not isinstance(patterns, list) or not patterns:
        errors.append("analysis.patterns must contain at least one analyzed pattern")
        return errors
    seen: set[str] = set()
    required = (
        "id", "source", "name", "category", "observation", "whyItWorks",
        "productRelevance", "proposedUse", "implementationImpact",
    )
    for pattern in patterns:
        pattern_id = pattern.get("id")
        if not pattern_id:
            errors.append("analysis.pattern.id is required")
        elif pattern_id in seen:
            errors.append(f"duplicate pattern id: {pattern_id}")
        else:
            seen.add(str(pattern_id))
        for field in required:
            if pattern.get(field) in (None, "", [], {}):
                errors.append(f"{pattern_id or '<unknown>'}.{field} is required")
        for field in PATTERN_LIST_FIELDS:
            if field not in pattern or not isinstance(pattern.get(field), list):
                errors.append(f"{pattern_id or '<unknown>'}.{field} must be an array")
        if pattern.get("category") not in PATTERN_CATEGORIES:
            errors.append(f"{pattern_id or '<unknown>'}.category is invalid")
        if pattern.get("implementationImpact") not in IMPLEMENTATION_IMPACTS:
            errors.append(f"{pattern_id or '<unknown>'}.implementationImpact is invalid")
        if pattern.get("source") not in source_locations:
            errors.append(f"{pattern_id or '<unknown>'}.source is not a supplied reference")
    return errors


def _normalize_capability_claims(
    root: Path,
    claims: Any,
) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    if not isinstance(claims, list):
        return normalized
    for raw_claim in claims:
        if not isinstance(raw_claim, dict) or not raw_claim.get("capability"):
            continue
        claim = dict(raw_claim)
        capability = str(claim["capability"])
        status = str(claim.get("status", "UNRESOLVED")).upper()
        if status not in {"VERIFIED", "ABSENT", "UNRESOLVED"}:
            status = "UNRESOLVED"
        validated_evidence: list[dict[str, str]] = []
        if status in {"VERIFIED", "ABSENT"}:
            for evidence in claim.get("evidence", []):
                if not isinstance(evidence, dict):
                    continue
                path_value = evidence.get("path")
                expected = evidence.get("sha256")
                if not path_value or not expected:
                    continue
                try:
                    path = ensure_within(root, path_value)
                except ValueError:
                    continue
                if path.is_file() and sha256_file(path) == expected:
                    validated_evidence.append({
                        "path": path.relative_to(root).as_posix(),
                        "sha256": str(expected),
                    })
            if not validated_evidence:
                status = "UNRESOLVED"
        if status == "ABSENT":
            if claim.get("evidenceMethod") != "repository-search" or not all(
                _valid_absence_search_receipt(root, evidence, capability)
                for evidence in validated_evidence
            ):
                status = "UNRESOLVED"
        claim["status"] = status
        claim["evidence"] = validated_evidence if status in {"VERIFIED", "ABSENT"} else []
        normalized[capability] = claim
    return normalized


def _valid_absence_search_receipt(
    root: Path,
    evidence: dict[str, str],
    capability: str,
) -> bool:
    try:
        path = ensure_within(root, evidence["path"])
    except (KeyError, ValueError):
        return False
    receipt = read_json(path, {}) or {}
    return bool(
        isinstance(receipt, dict)
        and receipt.get("schemaVersion") == 1
        and receipt.get("kind") == "repository-search"
        and receipt.get("capability") == capability
        and receipt.get("status") == "ABSENT"
        and Path(str(receipt.get("repositoryRoot", ""))).resolve() == root
        and receipt.get("scope") == "repository"
        and isinstance(receipt.get("queries"), list)
        and bool(receipt.get("queries"))
        and receipt.get("matches") == []
    )


def _decide_pattern(
    pattern: dict[str, Any],
    capability_claims: dict[str, dict[str, Any]],
    authorities: list[dict[str, Any]],
    design_system: dict[str, Any],
    memory_context: dict[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    missing: list[str] = []
    unresolved: list[str] = []
    for capability in pattern.get("requiredCapabilities", []):
        claim = capability_claims.get(str(capability))
        if not claim or claim.get("status") == "UNRESOLVED":
            unresolved.append(str(capability))
        elif claim.get("status") == "ABSENT":
            missing.append(str(capability))
    protected_risks = sorted(PROTECTED_RISK_FLAGS.intersection(pattern.get("riskFlags", [])))
    authority_conflicts = _blocking_authority_conflicts(pattern, authorities)
    memory_attention = _memory_attention(pattern, memory_context)
    impact = pattern.get("implementationImpact")
    if authority_conflicts:
        decision = "BLOCKED"
        reasons.append(
            "Conflicts with repository authority: "
            + ", ".join(item["location"] for item in authority_conflicts)
        )
    elif missing:
        decision = "DECLINE"
        reasons.append("Required product capability is absent: " + ", ".join(missing))
    elif protected_risks:
        decision = "DECLINE"
        reasons.append("Protected product risk would be introduced: " + ", ".join(protected_risks))
    elif impact in {"backend", "architecture"}:
        decision = "BLOCKED"
        reasons.append(f"Reference adoption cannot authorize {impact} change")
    elif unresolved:
        decision = "DEFER"
        reasons.append("Required product capability is unresolved: " + ", ".join(unresolved))
    elif memory_attention:
        decision = "DEFER"
        reasons.append("Institutional memory requires review: " + ", ".join(memory_attention))
    elif design_system["status"] == "CONFLICTED" and impact in {"visual-only", "component", "workflow"}:
        decision = "DEFER"
        reasons.append("Existing design-system authorities conflict and must be converged first")
    elif design_system["status"] == "NEEDS_ALIGNMENT" and impact in {"component", "workflow"}:
        decision = "DEFER"
        reasons.append("Existing design-system evidence needs alignment before component or workflow extension")
    elif pattern.get("identityElements") or impact in {"component", "workflow"}:
        decision = "ADAPT"
        reasons.append("Transfer the pattern without copying identity or changing product authority")
    else:
        decision = "ADOPT"
        reasons.append("Pattern is evidence-bound and fits existing product capability")
    return {
        "patternId": pattern.get("id"),
        "source": pattern.get("source"),
        "name": pattern.get("name"),
        "decision": decision,
        "reasons": reasons,
        "requiredCapabilities": pattern.get("requiredCapabilities", []),
        "riskFlags": pattern.get("riskFlags", []),
        "implementationImpact": impact,
        "proposedUse": pattern.get("proposedUse"),
        "authorityConflicts": authority_conflicts,
        "memoryAttention": memory_attention,
    }


def _build_adoption_contract(
    root: Path,
    task: str,
    decisions: list[dict[str, Any]],
    profile_name: str | None,
    surface: str | None,
) -> dict[str, Any]:
    workflow = build_workflow(
        str(root),
        task,
        profile_name,
        surface,
    )
    payload = dict(workflow["contract"])
    permitted = [item for item in decisions if item["decision"] in {"ADOPT", "ADAPT"}]
    payload["change"] = [
        str(item["proposedUse"])
        for item in permitted
        if item.get("proposedUse")
    ]
    payload["reuse"] = list(dict.fromkeys([
        *payload["reuse"],
        *(
            ["existing tokens, components, and runtime authority"]
            if any(item["decision"] == "ADAPT" for item in permitted)
            else []
        ),
    ]))
    payload["doNotTouch"] = list(dict.fromkeys([
        *payload["doNotTouch"],
        "unsupported product capabilities, protected repository authority, and source identity",
    ]))
    payload["acceptanceCriteria"] = [
        *payload["acceptanceCriteria"],
        *[
            f"Rendered evidence verifies {item['name']} as {item['decision']} without authority expansion."
            for item in permitted
        ],
    ]
    payload["relevantDesignDecisions"] = [item["patternId"] for item in permitted]
    return create_contract(payload)


def _blocking_authority_conflicts(
    pattern: dict[str, Any],
    authorities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    terms = {
        _normalize_text(str(item))
        for item in [pattern.get("name"), *pattern.get("keywords", [])]
        if item
    }
    terms.discard("")
    conflicts: list[dict[str, Any]] = []
    negative_markers = (
        "do not", "must not", "never", "cannot", "prohibit", "reject", "blocked",
    )
    authoritative_statuses = {
        "accepted", "approved", "blocked", "current", "enforced", "scoped",
    }
    for source in authorities:
        for statement in source.get("statements", []):
            normalized = _normalize_text(statement.get("text", ""))
            if statement.get("status") not in authoritative_statuses:
                continue
            if not any(marker in normalized for marker in negative_markers):
                continue
            if not any(term in normalized for term in terms):
                continue
            conflicts.append({
                "authorityId": source["id"],
                "kind": source["kind"],
                "location": f"{source['path']}:{statement['line']}",
                "statement": statement["text"],
            })
    return conflicts


def _retrieve_memory_context(
    root: Path,
    product: str | None,
    surface: str | None,
) -> dict[str, Any]:
    max_records = 20
    if not (root / ".design/memory/product-rules.json").is_file():
        return {
            "status": "NOT_CONFIGURED",
            "product": product,
            "surface": surface,
            "maxRecords": max_records,
            "inherited_rules": [],
            "decisions": [],
            "active_exceptions": [],
            "rejected_outcomes": [],
            "unresolved_debt": [],
            "stale_records": [],
            "conflicts": [],
            "bounded": False,
            "total_available": 0,
        }
    audit = audit_memory(root)
    context = retrieve_context(
        root,
        product=product,
        surface=surface,
        max_records=max_records,
    ).to_dict()
    return {
        "status": "AVAILABLE" if audit["status"] == "PASS" else "INVALID",
        "maxRecords": max_records,
        "audit": audit,
        **context,
    }


def _memory_attention(
    pattern: dict[str, Any],
    memory_context: dict[str, Any],
) -> list[str]:
    terms = {
        _normalize_text(str(item))
        for item in [pattern.get("name"), *pattern.get("keywords", [])]
        if item
    }
    terms.discard("")
    attention: list[str] = []
    for debt in memory_context.get("unresolved_debt", []):
        description = _normalize_text(str(debt.get("description", "")))
        if any(term in description for term in terms):
            attention.append(f"open debt {debt.get('id')}")
    for outcome in memory_context.get("rejected_outcomes", []):
        text = _normalize_text(
            " ".join(str(outcome.get(field, "")) for field in ("reason", "lesson"))
        )
        if any(term in text for term in terms):
            attention.append(f"rejected outcome {outcome.get('id')}")
    linked_ids = set(pattern.get("memoryDecisionIds", []))
    for stale in memory_context.get("stale_records", []):
        if stale.get("id") in linked_ids:
            attention.append(f"stale {stale.get('type')} {stale.get('id')}")
    return attention


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _image_dimensions(path: Path) -> dict[str, int] | None:
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return {"width": width, "height": height}
    if data[:6] in {b"GIF87a", b"GIF89a"} and len(data) >= 10:
        width, height = struct.unpack("<HH", data[6:10])
        return {"width": width, "height": height}
    if data.startswith(b"\xff\xd8"):
        offset = 2
        while offset + 9 < len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            marker = data[offset + 1]
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                height, width = struct.unpack(">HH", data[offset + 5:offset + 9])
                return {"width": width, "height": height}
            if offset + 4 > len(data):
                break
            segment_length = struct.unpack(">H", data[offset + 2:offset + 4])[0]
            offset += max(2, segment_length + 2)
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP" and len(data) >= 30:
        chunk = data[12:16]
        if chunk == b"VP8X":
            width = int.from_bytes(data[24:27], "little") + 1
            height = int.from_bytes(data[27:30], "little") + 1
            return {"width": width, "height": height}
        if chunk == b"VP8L" and len(data) >= 25:
            bits = int.from_bytes(data[21:25], "little")
            return {"width": (bits & 0x3FFF) + 1, "height": ((bits >> 14) & 0x3FFF) + 1}
    if path.suffix.lower() == ".svg":
        text = data.decode("utf-8", errors="ignore")[:4096]
        width = re.search(r"\bwidth=[\"']([0-9.]+)", text)
        height = re.search(r"\bheight=[\"']([0-9.]+)", text)
        if width and height:
            return {"width": int(float(width.group(1))), "height": int(float(height.group(1)))}
        view_box = re.search(
            r"\bviewBox=[\"']\s*[-0-9.]+[ ,]+[-0-9.]+[ ,]+([0-9.]+)[ ,]+([0-9.]+)[\"']",
            text,
        )
        if view_box:
            return {"width": int(float(view_box.group(1))), "height": int(float(view_box.group(2)))}
    return None


def _report_id(report: dict[str, Any]) -> str:
    identity = {key: value for key, value in report.items() if key != "id"}
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16].upper()
    return f"DAR-{digest}"


def _audit_hash_binding(
    root: Path,
    label: str,
    binding: dict[str, Any],
    errors: list[str],
) -> None:
    path_value = binding.get("path")
    expected = binding.get("sha256")
    if not path_value or not expected:
        errors.append(f"{label}: path and sha256 are required")
        return
    try:
        path = ensure_within(root, path_value)
    except ValueError as error:
        errors.append(f"{label}: {error}")
        return
    if not path.is_file():
        errors.append(f"{label}: file missing")
    elif sha256_file(path) != expected:
        errors.append(f"{label}: hash mismatch")


def _analysis_request(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "task": report["task"],
        "sources": report["sources"],
        "requiredAnalyzerFields": ["type", "name", "observedAt"],
        "requiredPatternFields": [
            "id", "source", "name", "category", "observation", "whyItWorks",
            "productRelevance", "proposedUse", "keywords", "requiredCapabilities",
            "riskFlags", "identityElements", "implementationImpact",
        ],
        "decisionAuthority": (
            "The analyzer supplies observations only; repository rules decide adoption."
        ),
    }


def _authority_id(kind: str, relative: str) -> str:
    digest = hashlib.sha256(f"{kind}:{relative}".encode("utf-8")).hexdigest()[:12].upper()
    return f"AUTH-{digest}"


def _extract_statements(path: Path, kind: str) -> list[dict[str, Any]]:
    statements: list[dict[str, Any]] = []
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8", errors="ignore").splitlines(),
        start=1,
    ):
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        statements.append({
            "line": line_number,
            "status": _statement_status(text, kind),
            "text": text,
        })
        if len(statements) >= 80:
            break
    return statements


def _statement_status(text: str, kind: str) -> str:
    if text.startswith("{"):
        try:
            record = json.loads(text)
        except json.JSONDecodeError:
            record = None
        if isinstance(record, dict) and record.get("status"):
            return str(record["status"]).lower()
    explicit = re.search(r"\[status:\s*([a-z-]+)\]", text, flags=re.IGNORECASE)
    if explicit:
        return explicit.group(1).lower()
    lowered = text.lower()
    for status in ("accepted", "approved", "blocked", "deferred", "rejected", "cancelled"):
        if re.search(rf"\b{status}\b", lowered):
            return status
    if re.match(r"^-\s*\[x\]", lowered):
        return "completed"
    if re.match(r"^-\s*\[\s\]", lowered):
        return "proposed"
    if kind == "hook":
        return "enforced"
    if kind in {"agent-governance", "custom-instructions"}:
        return "scoped"
    return "current"
