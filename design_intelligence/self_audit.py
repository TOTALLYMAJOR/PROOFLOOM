from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .adoption import audit_adoption_report
from .baselines import audit_baseline_review_request, audit_baselines
from .contracts import load_and_validate_contract
from .control_plane import architecture_graph, validate_control_plane
from .governance import verify_governance_convergence
from .memory import audit_memory
from .planes import audit_planes
from .quality import audit_thresholds, load_thresholds
from .registry import audit_component_registry
from .review_lifecycle import (
    audit_baseline_review_receipt,
    evaluate_baseline_review_lifecycle,
    load_review_policy,
)


REQUIRED_V2_PATHS = (
    ".design/memory/decisions.jsonl",
    ".design/memory/outcomes.jsonl",
    ".design/memory/exceptions.jsonl",
    ".design/memory/debt.jsonl",
    ".design/memory/product-rules.json",
    ".design/memory/component-registry.json",
    ".design/quality/thresholds.json",
    ".design/baselines/manifest.json",
    "scripts/design/visual-qa.mjs",
    "scripts/design/prove-repairs.mjs",
    "tests/design/scenarios/design-department-surface.json",
    "docs/design/DESIGN-QUALITY.md",
)

REQUIRED_V3_SLICE0_PATHS = (
    ".design/memory/schemas/baseline-review-request.schema.json",
    ".design/memory/schemas/baseline-review-receipt.schema.json",
    ".design/baselines/review-policy.json",
    ".github/workflows/design-ci.yml",
    "design_intelligence/data/schemas/baseline-review-request.schema.json",
    "design_intelligence/data/schemas/baseline-review-receipt.schema.json",
    "docs/design/AUTONOMOUS-DESIGN-DEPARTMENT-V3.md",
)

REQUIRED_V3_MISSION_PATHS = (
    "design_intelligence/missions.py",
    "scripts/design-intelligence",
    "scripts/install",
    "skills/design-language/references/mission-workflow.md",
    "docs/RELEASE-REPORT-3.0.0.md",
)

REQUIRED_V4_ADOPTION_PATHS = (
    ".design/memory/schemas/reference-analysis.schema.json",
    ".design/memory/schemas/design-adoption-report.schema.json",
    "design_intelligence/data/schemas/reference-analysis.schema.json",
    "design_intelligence/data/schemas/design-adoption-report.schema.json",
    "design_intelligence/adoption.py",
    "scripts/design/capture-reference.mjs",
    "docs/design/DESIGN-ADOPTION-GATE.md",
)

REQUIRED_CONTROL_PLANE_PATHS = (
    "VERSION",
    "devctl.yaml",
    ".dev/VERSION",
    "design_intelligence/control_plane.py",
    "design_intelligence/architecture_graph.py",
    "design_intelligence/devctl_cli.py",
    "design_intelligence/data/schemas/architecture-graph.schema.json",
    "design_intelligence/data/schemas/devctl.schema.json",
    "design_intelligence/data/schemas/task-packet.schema.json",
    "design_intelligence/planes.py",
    "design_intelligence/data/defaults/industry-standards.json",
    "design_intelligence/data/schemas/intent-index.schema.json",
    "design_intelligence/data/schemas/standards-profile.schema.json",
    "design_intelligence/data/schemas/model-routing.schema.json",
    "design_intelligence/data/schemas/backlog-portfolio.schema.json",
    ".dev/intent-index.json",
    ".dev/standards-profile.json",
    ".dev/model-routing.json",
    "scripts/devctl",
    "docs/CONTROL-PLANE-PHASES-0-3.md",
    "docs/CONTROL-PLANE-PHASE-4.md",
    "docs/CONTROL-PLANE-INTENT-ARCHITECTURE-INTELLIGENCE.md",
    "docs/CONTROL-PLANE-ROLES.md",
    "docs/CONTROL-PLANE-ARCHITECTURE-GRAPH.md",
    "docs/RELEASE-REPORT-4.0.0.md",
    "docs/architecture/ADR-0003-bounded-architecture-impact-graph.md",
)

REQUIRED_V5_GOVERNANCE_PATHS = (
    "design_intelligence/governance.py",
    "docs/REPOSITORY-REHABILITATION-AND-FINALIZATION.md",
    "docs/RELEASE-REPORT-5.0.0.md",
    ".dev/governance/governance-map.json",
    ".dev/governance/repository-adapter.json",
    ".dev/governance/convergence-manifest.json",
    ".dev/governance/rehabilitation-plan.json",
    ".dev/governance/HUMAN-READOUT.md",
    ".dev/governance/OWNER-RATIFICATION.md",
)

REQUIRED_AGENTIC_PATHS = (
    "design_intelligence/agentic.py",
    "design_intelligence/data/schemas/authority-capsule.schema.json",
    "design_intelligence/data/schemas/ux-state-graph.schema.json",
    "design_intelligence/data/schemas/counterfactual-report.schema.json",
    "design_intelligence/data/schemas/design-arena-report.schema.json",
    "design_intelligence/data/schemas/outcome-assessment.schema.json",
    "design_intelligence/data/schemas/outcome-ratification-receipt.schema.json",
    "design_intelligence/outcome_lifecycle.py",
    "scripts/design/verify-cross-browser-policy.mjs",
    "tests/test_agentic_capabilities.py",
    "tests/test_outcome_lifecycle.py",
    "docs/AGENTIC-DEVELOPMENT.md",
    "docs/FEATURE_MATRIX.md",
)

V1_SKILLS = (
    "design-language",
    "ux-architect",
    "reference-intelligence",
    "visual-review",
    "design-linter",
)


def run_self_audit(repository_root: str | Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    checks: dict[str, dict[str, Any]] = {}
    required_paths = (
        REQUIRED_V2_PATHS
        + REQUIRED_V3_SLICE0_PATHS
        + REQUIRED_V3_MISSION_PATHS
        + REQUIRED_V4_ADOPTION_PATHS
        + REQUIRED_CONTROL_PLANE_PATHS
        + REQUIRED_V5_GOVERNANCE_PATHS
        + REQUIRED_AGENTIC_PATHS
    )
    missing = [path for path in required_paths if not (root / path).exists()]
    checks["requiredInfrastructure"] = {"status": "PASS" if not missing else "FAIL", "missing": missing}

    checks["governanceConvergence"] = verify_governance_convergence(root)

    control_plane = validate_control_plane(root)
    checks["controlPlane"] = control_plane
    if control_plane.get("status") == "PASS":
        from .control_plane import load_manifest

        checks["controlPlanePlanes"] = audit_planes(root, load_manifest(root))
        graph = architecture_graph(root)
        checks["architectureGraph"] = {
            key: graph[key]
            for key in (
                "schemaVersion",
                "status",
                "bounded",
                "limits",
                "sourceFilesScanned",
                "discoveredNodeCount",
                "nodeCount",
                "edgeCount",
                "nodeCounts",
                "graphSha256",
                "truncated",
                "claimBoundary",
                "errors",
                "warnings",
            )
            if key in graph
        }
    else:
        checks["controlPlanePlanes"] = {
            "status": "FAIL",
            "errors": ["Plane audit requires a valid control-plane manifest"],
        }
        checks["architectureGraph"] = {
            "status": "FAIL",
            "errors": ["Architecture graph audit requires a valid control-plane manifest"],
        }

    skill_errors: list[str] = []
    for skill in V1_SKILLS:
        path = root / "skills" / skill / "SKILL.md"
        if not path.is_file():
            skill_errors.append(f"Missing V1 skill: {skill}")
        elif f"name: {skill}" not in path.read_text(encoding="utf-8"):
            skill_errors.append(f"V1 skill identity changed: {skill}")
    checks["v1Skills"] = {"status": "PASS" if not skill_errors else "FAIL", "errors": skill_errors}

    memory = audit_memory(root)
    checks["memory"] = memory
    baselines = audit_baselines(root)
    checks["baselines"] = baselines
    request_paths = sorted((root / "artifacts/design/baseline-requests").glob("*.json"))
    request_errors: list[str] = []
    request_statuses: dict[str, str | None] = {}
    for path in request_paths:
        result = audit_baseline_review_request(root, path)
        request_statuses[path.name] = result.get("requestStatus")
        request_errors.extend(f"{path.name}: {error}" for error in result.get("errors", []))
    if not request_paths:
        request_errors.append("No baseline review request evidence found")
    checks["baselineReviewRequests"] = {
        "status": "PASS" if not request_errors else "FAIL",
        "count": len(request_paths),
        "requests": request_statuses,
        "errors": request_errors,
    }
    receipt_paths = sorted((root / "artifacts/design/baseline-decisions").glob("*.json"))
    receipt_errors: list[str] = []
    receipt_decisions: dict[str, str | None] = {}
    for path in receipt_paths:
        try:
            result = audit_baseline_review_receipt(root, path)
        except ValueError as error:
            receipt_decisions[path.name] = None
            receipt_errors.append(f"{path.name}: {error}")
        else:
            receipt_decisions[path.name] = result.get("decision")
            receipt_errors.extend(
                f"{path.name}: {error}" for error in result.get("errors", [])
            )
    checks["baselineReviewReceipts"] = {
        "status": "PASS" if not receipt_errors else "FAIL",
        "count": len(receipt_paths),
        "receipts": receipt_decisions,
        "errors": receipt_errors,
    }
    try:
        review_policy = load_review_policy(root)
        policy_errors: list[str] = []
    except ValueError as error:
        review_policy = None
        policy_errors = [str(error)]
    checks["baselineReviewPolicy"] = {
        "status": "PASS" if not policy_errors else "FAIL",
        "policy": review_policy,
        "errors": policy_errors,
    }
    try:
        lifecycle = evaluate_baseline_review_lifecycle(root)
    except ValueError as error:
        lifecycle = {"status": "FAIL", "errors": [str(error)]}
    checks["baselineReviewLifecycle"] = lifecycle

    workflow_path = root / ".github/workflows/design-ci.yml"
    workflow = workflow_path.read_text(encoding="utf-8") if workflow_path.is_file() else ""
    required_workflow_markers = (
        "pull_request:", "contents: read", "design:ci:quick", "design:ci:standard", "design:ci:full",
    )
    forbidden_workflow_markers = ("pull_request_target", "baseline promote", "repair --apply")
    workflow_errors = [
        f"Remote CI missing policy marker: {marker}"
        for marker in required_workflow_markers
        if marker not in workflow
    ]
    workflow_errors.extend(
        f"Remote CI contains forbidden authority: {marker}"
        for marker in forbidden_workflow_markers
        if marker in workflow
    )
    checks["remoteCI"] = {
        "status": "PASS" if not workflow_errors else "FAIL",
        "errors": workflow_errors,
    }
    threshold_errors = audit_thresholds(load_thresholds(root / ".design/quality/thresholds.json"))
    checks["thresholds"] = {"status": "PASS" if not threshold_errors else "FAIL", "errors": threshold_errors}
    registry = audit_component_registry(root)
    checks["componentRegistry"] = registry

    contract_paths = sorted((root / "artifacts/design/briefs").glob("*.json")) if (root / "artifacts/design/briefs").exists() else []
    contract_errors: list[str] = []
    for path in contract_paths:
        _, errors = load_and_validate_contract(path)
        contract_errors.extend(f"{path.name}: {error}" for error in errors)
    if not contract_paths:
        contract_errors.append("No design contract evidence found")
    checks["designContracts"] = {"status": "PASS" if not contract_errors else "FAIL", "errors": contract_errors}

    adoption_paths = sorted(
        (root / "artifacts/design/adoptions").glob("*/adoption-report.json")
    ) if (root / "artifacts/design/adoptions").exists() else []
    adoption_errors: list[str] = []
    adoption_warnings: list[str] = []
    adoption_statuses: dict[str, str | None] = {}
    governed_adoptions: list[tuple[str, tuple[Any, Any, Any], dict[str, Any]]] = []
    current_adoption_reports = 0
    for path in adoption_paths:
        relative = path.relative_to(root).as_posix()
        try:
            result = audit_adoption_report(root, path)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            adoption_statuses[relative] = None
            adoption_errors.append(f"{relative}: {error}")
        else:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            legacy = isinstance(loaded, dict) and (
                "memoryRequired" not in loaded or "governanceConstraints" not in loaded
            )
            if legacy:
                adoption_statuses[relative] = "LEGACY_BLOCKED"
                adoption_warnings.append(
                    f"{relative}: legacy report remains historical evidence and cannot authorize implementation"
                )
            else:
                scope = (loaded.get("task"), loaded.get("profile"), loaded.get("surface"))
                governed_adoptions.append((relative, scope, result))
    current_scopes = {
        scope
        for _, scope, result in governed_adoptions
        if result.get("status") == "PASS"
    }
    for relative, scope, result in governed_adoptions:
        if result.get("status") == "PASS":
            adoption_statuses[relative] = "PASS"
            current_adoption_reports += 1
        elif scope in current_scopes:
            adoption_statuses[relative] = "HISTORICAL_BLOCKED"
            adoption_warnings.extend(
                f"{relative}: historical report cannot authorize implementation: {error}"
                for error in result.get("errors", [])
            )
        else:
            adoption_statuses[relative] = result.get("status")
            adoption_errors.extend(
                f"{relative}: {error}" for error in result.get("errors", [])
            )
    if not adoption_paths:
        adoption_errors.append("No governed design adoption report evidence found")
    elif current_adoption_reports == 0:
        adoption_errors.append("No current governed design adoption report passed replay audit")
    checks["designAdoptions"] = {
        "status": "PASS" if not adoption_errors else "FAIL",
        "count": len(adoption_paths),
        "current": current_adoption_reports,
        "reports": adoption_statuses,
        "errors": adoption_errors,
        "warnings": adoption_warnings,
    }

    repair_evidence = sorted((root / "artifacts/design/evidence/repair-cycles").glob("*/evidence.json")) if (root / "artifacts/design/evidence/repair-cycles").exists() else []
    valid_cycles = 0
    cycle_errors: list[str] = []
    for path in repair_evidence:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("beforeStatus") == "FAIL" and payload.get("repairStatus") == "APPLIED" and payload.get("afterStatus") == "PASS":
            valid_cycles += 1
        else:
            cycle_errors.append(f"Incomplete repair proof: {path.relative_to(root)}")
    if valid_cycles < 3:
        cycle_errors.append(f"Expected at least 3 proven repair cycles; found {valid_cycles}")
    checks["repairCycles"] = {"status": "PASS" if not cycle_errors else "FAIL", "count": valid_cycles, "errors": cycle_errors}

    quality_path = root / ".design/quality/latest-score.json"
    quality = json.loads(quality_path.read_text(encoding="utf-8")) if quality_path.is_file() else {}
    quality_errors = [] if quality.get("status") == "PASS" else ["Latest deterministic quality report is not PASS"]
    checks["quality"] = {"status": "PASS" if not quality_errors else "FAIL", "errors": quality_errors, "score": quality.get("score")}

    failures = [name for name, check in checks.items() if check.get("status") != "PASS"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "proofBoundary": "Local repository, deterministic test, and rendered fixture evidence only; no production product acceptance is claimed.",
    }
