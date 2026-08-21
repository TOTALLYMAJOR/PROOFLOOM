from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .baselines import audit_baselines
from .contracts import load_and_validate_contract
from .memory import audit_memory
from .quality import audit_thresholds, load_thresholds
from .registry import audit_component_registry


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
    missing = [path for path in REQUIRED_V2_PATHS if not (root / path).exists()]
    checks["requiredInfrastructure"] = {"status": "PASS" if not missing else "FAIL", "missing": missing}

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
