from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .memory import memory_root
from .storage import atomic_write_json, ensure_within, read_json, read_jsonl, sha256_file


BASELINE_REVIEW_AUTHORITY = "human-required"


def create_baseline_review_request(
    repository_root: str | Path,
    scenario_id: str,
    product: str,
    qa_report_path: str | Path,
    model_review_path: str | Path,
    candidate_root: str | Path,
    requested_by: str,
    output_path: str | Path,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    qa_path = ensure_within(root, qa_report_path)
    model_path = ensure_within(root, model_review_path)
    candidates_root = ensure_within(root, candidate_root)
    destination = ensure_within(root, output_path)
    if not qa_path.is_file():
        raise ValueError(f"QA report not found: {_relative(root, qa_path)}")
    if not model_path.is_file():
        raise ValueError(f"Model review not found: {_relative(root, model_path)}")
    if not candidates_root.is_dir():
        raise ValueError(f"Candidate root not found: {_relative(root, candidates_root)}")
    if not scenario_id.strip() or not product.strip() or not requested_by.strip():
        raise ValueError("scenario, product, and requested-by are required")

    qa = read_json(qa_path, {}) or {}
    model = read_json(model_path, {}) or {}
    thresholds = read_json(root / ".design/quality/thresholds.json", {}) or {}
    required_viewports = int(thresholds.get("requiredViewportCount", 5))
    blockers = _review_blockers(qa, model)

    candidates, candidate_blockers = _collect_candidates(root, qa, candidates_root, required_viewports)
    blockers.extend(candidate_blockers)

    source_revision = qa.get("sourceRevision") or {}
    request_id = _review_request_id(scenario_id, source_revision, candidates)
    unique_blockers = sorted(set(blockers))
    request = {
        "schemaVersion": 1,
        "id": request_id,
        "scenarioId": scenario_id,
        "product": product,
        "surface": qa.get("surface") or model.get("surface") or scenario_id,
        "status": "BLOCKED" if unique_blockers else "REVIEWABLE",
        "requestedBy": requested_by,
        "requestedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "promotionAuthority": BASELINE_REVIEW_AUTHORITY,
        "baselineMutationPerformed": False,
        "sourceRevision": source_revision,
        "qaEvidence": {
            "path": _relative(root, qa_path),
            "sha256": sha256_file(qa_path),
            "status": qa.get("status"),
        },
        "modelEvidence": {
            "path": _relative(root, model_path),
            "sha256": sha256_file(model_path),
            "verdict": model.get("verdict"),
            "severity": model.get("severity"),
        },
        "candidateRoot": _relative(root, candidates_root),
        "candidates": candidates,
        "blockers": unique_blockers,
        "requiredHumanApprovals": [
            "Product owner visual acceptance",
            "Manual semantic accessibility review",
            "Accepted design-memory decision authorizing baseline promotion",
        ],
    }
    atomic_write_json(destination, request)
    return request


def audit_baseline_review_request(
    repository_root: str | Path,
    request_path: str | Path,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    source = ensure_within(root, request_path)
    request = read_json(source, {}) or {}
    errors: list[str] = []
    required = (
        "id", "scenarioId", "product", "surface", "status", "requestedBy", "requestedAt",
        "promotionAuthority", "sourceRevision", "qaEvidence", "modelEvidence", "candidateRoot",
        "candidates", "requiredHumanApprovals",
    )
    errors.extend(f"request.{field} is required" for field in required if request.get(field) in (None, "", [], {}))
    if not isinstance(request.get("blockers"), list):
        errors.append("request.blockers must be an array")
    if request.get("baselineMutationPerformed") is not False:
        errors.append("request.baselineMutationPerformed must be false")
    if request.get("promotionAuthority") != BASELINE_REVIEW_AUTHORITY:
        errors.append(f"request.promotionAuthority must be {BASELINE_REVIEW_AUTHORITY}")
    if request.get("status") not in {"REVIEWABLE", "BLOCKED"}:
        errors.append("request.status must be REVIEWABLE or BLOCKED")
    blockers = request.get("blockers") or []
    if request.get("status") == "REVIEWABLE" and blockers:
        errors.append("REVIEWABLE requests cannot contain blockers")
    if request.get("status") == "BLOCKED" and not blockers:
        errors.append("BLOCKED requests require at least one blocker")

    checked = 0
    evidence_paths: dict[str, Path] = {}
    for evidence_name in ("qaEvidence", "modelEvidence"):
        evidence = request.get(evidence_name) or {}
        checked += _audit_hash(root, evidence_name, evidence, errors)
        if evidence.get("path"):
            evidence_path = _safe_within(root, evidence["path"], evidence_name, errors)
            if evidence_path:
                evidence_paths[evidence_name] = evidence_path
    candidate_root_value = request.get("candidateRoot")
    candidate_root_path = (
        _safe_within(root, candidate_root_value, "candidateRoot", errors)
        if candidate_root_value else None
    )
    seen_paths: set[str] = set()
    for viewport, candidate in (request.get("candidates") or {}).items():
        path_value = candidate.get("path")
        if path_value in seen_paths:
            errors.append(f"candidates.{viewport}: duplicate path")
        seen_paths.add(path_value)
        if path_value:
            candidate_path = _safe_within(root, path_value, f"candidates.{viewport}", errors)
            if candidate_path and candidate_root_path and candidate_path != candidate_root_path and candidate_root_path not in candidate_path.parents:
                errors.append(f"candidates.{viewport}: path is outside candidateRoot")
        checked += _audit_hash(root, f"candidates.{viewport}", candidate, errors)

    qa = read_json(evidence_paths.get("qaEvidence", root / "missing"), {}) or {}
    model = read_json(evidence_paths.get("modelEvidence", root / "missing"), {}) or {}
    if request.get("sourceRevision") != qa.get("sourceRevision"):
        errors.append("request.sourceRevision does not match QA evidence")
    if (request.get("qaEvidence") or {}).get("status") != qa.get("status"):
        errors.append("request.qaEvidence.status does not match QA evidence")
    model_evidence = request.get("modelEvidence") or {}
    if model_evidence.get("verdict") != model.get("verdict"):
        errors.append("request.modelEvidence.verdict does not match model evidence")
    if model_evidence.get("severity") != model.get("severity"):
        errors.append("request.modelEvidence.severity does not match model evidence")
    thresholds = read_json(root / ".design/quality/thresholds.json", {}) or {}
    required_viewports = int(thresholds.get("requiredViewportCount", 5))
    expected_candidate_entries, candidate_blockers = _collect_candidates(
        root,
        qa,
        candidate_root_path or root,
        required_viewports,
    )
    expected_candidates = {
        viewport: candidate.get("path")
        for viewport, candidate in expected_candidate_entries.items()
    }
    actual_candidates = {
        viewport: candidate.get("path")
        for viewport, candidate in (request.get("candidates") or {}).items()
    }
    if actual_candidates != expected_candidates:
        errors.append("request candidates do not match QA evidence")
    if len(actual_candidates) < required_viewports:
        errors.append(f"request requires {required_viewports} candidate viewports")
    expected_blockers = sorted(set(_review_blockers(qa, model) + candidate_blockers))
    if sorted(set(blockers)) != expected_blockers:
        errors.append("request.blockers do not match the bound QA, model, and candidate evidence")
    expected_status = "BLOCKED" if expected_blockers else "REVIEWABLE"
    if request.get("status") != expected_status:
        errors.append(f"request.status must be {expected_status} for the bound evidence")
    expected_id = _review_request_id(
        str(request.get("scenarioId") or ""),
        request.get("sourceRevision") or {},
        request.get("candidates") or {},
    )
    if request.get("id") != expected_id:
        errors.append("request.id does not match its evidence identity")
    return {
        "status": "PASS" if not errors else "FAIL",
        "requestStatus": request.get("status"),
        "checked": checked,
        "errors": errors,
    }


def promote_baseline(
    repository_root: str | Path,
    scenario_id: str,
    current_root: str | Path,
    approval_path: str | Path,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    current = Path(current_root).resolve()
    approval = read_json(approval_path, {}) or {}
    errors = _validate_approval(root, approval)
    if errors:
        raise ValueError("Baseline promotion denied: " + "; ".join(errors))
    images = sorted(current.glob("*/current.png"))
    if not images:
        raise ValueError(f"No current screenshots found below {current}")
    baseline_root = root / ".design/baselines" / scenario_id
    manifest_path = root / ".design/baselines/manifest.json"
    manifest = read_json(manifest_path, {"schemaVersion": 1, "scenarios": {}}) or {"schemaVersion": 1, "scenarios": {}}
    entries: dict[str, Any] = {}
    for image in images:
        viewport = image.parent.name
        destination = baseline_root / viewport / "baseline.png"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(image, destination)
        entries[viewport] = {
            "path": destination.relative_to(root).as_posix(),
            "sha256": sha256_file(destination),
        }
    manifest.setdefault("scenarios", {})[scenario_id] = {
        "approvedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "approval": approval,
        "viewports": entries,
    }
    atomic_write_json(manifest_path, manifest)
    return manifest["scenarios"][scenario_id]


def audit_baselines(repository_root: str | Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    manifest = read_json(root / ".design/baselines/manifest.json", {}) or {}
    errors: list[str] = []
    checked = 0
    for scenario_id, scenario in manifest.get("scenarios", {}).items():
        approval_errors = _validate_approval(root, scenario.get("approval", {}))
        errors.extend(f"{scenario_id}: {error}" for error in approval_errors)
        for viewport, entry in scenario.get("viewports", {}).items():
            path = root / entry.get("path", "")
            checked += 1
            if not path.is_file():
                errors.append(f"{scenario_id}/{viewport}: baseline missing")
            elif sha256_file(path) != entry.get("sha256"):
                errors.append(f"{scenario_id}/{viewport}: baseline hash mismatch")
    return {"status": "PASS" if not errors else "FAIL", "checked": checked, "errors": errors}


def _validate_approval(repository_root: Path, approval: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = ("decisionId", "reason", "authorizedBy", "validationStatus", "validationEvidence")
    for field in required:
        if not approval.get(field):
            errors.append(f"approval.{field} is required")
    if approval.get("validationStatus") != "PASS":
        errors.append("approval.validationStatus must be PASS")
    authority = str(approval.get("authorizedBy", "")).lower()
    if not authority or authority.startswith("agent") or authority == "quality-gate":
        errors.append("baseline promotion requires explicit human authority")
    decisions = read_jsonl(memory_root(repository_root) / "decisions.jsonl")
    accepted = [item for item in decisions if item.get("id") == approval.get("decisionId") and item.get("status") == "accepted"]
    if not accepted:
        errors.append(f"accepted decision not found: {approval.get('decisionId')}")
    return errors


def _review_blockers(qa: dict[str, Any], model: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    totals = qa.get("totals") or {}
    source_revision = qa.get("sourceRevision") or {}
    if qa.get("status") != "PASS":
        blockers.append(f"QA status is {qa.get('status') or 'missing'}, not PASS")
    if not source_revision.get("commitSha"):
        blockers.append("QA source revision has no commit SHA")
    for field, label in (
        ("criticalAccessibilityViolations", "critical accessibility violations"),
        ("seriousAccessibilityViolations", "serious accessibility violations"),
        ("containmentFailures", "viewport containment failures"),
    ):
        count = int(totals.get(field, 0))
        if count:
            blockers.append(f"{count} {label}")
    for prefix in ("domAssertions", "contractAssertions"):
        passed = int(totals.get(f"{prefix}Passed", 0))
        total = int(totals.get(f"{prefix}Total", 0))
        if total <= 0 or passed != total:
            blockers.append(f"{prefix} require complete passing evidence; found {passed}/{total}")
    failing_viewports = [str(item.get("id") or "<unknown>") for item in qa.get("viewports", []) if item.get("status") != "PASS"]
    if failing_viewports:
        blockers.append("viewport QA failed: " + ", ".join(failing_viewports))
    if model.get("verdict") == "FAIL":
        blockers.append(f"model visual review failed at {model.get('severity') or 'unknown severity'}")
    if model.get("verdict") not in {"PASS", "WARN", "FAIL"}:
        blockers.append("model visual review verdict is missing or invalid")
    return blockers


def _audit_hash(root: Path, label: str, entry: dict[str, Any], errors: list[str]) -> int:
    path_value = entry.get("path")
    expected = entry.get("sha256")
    if not path_value or not expected:
        errors.append(f"{label}: path and sha256 are required")
        return 0
    path = _safe_within(root, path_value, label, errors)
    if not path:
        return 1
    if not path.is_file():
        errors.append(f"{label}: file missing")
    elif sha256_file(path) != expected:
        errors.append(f"{label}: hash mismatch")
    return 1


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _collect_candidates(
    root: Path,
    qa: dict[str, Any],
    candidate_root: Path,
    required_viewports: int,
) -> tuple[dict[str, dict[str, str]], list[str]]:
    candidates: dict[str, dict[str, str]] = {}
    blockers: list[str] = []
    for viewport in qa.get("viewports", []):
        screenshot_value = (viewport.get("artifacts") or {}).get("currentScreenshot")
        viewport_id = str(viewport.get("id") or "").strip()
        if not screenshot_value:
            blockers.append(f"viewport {viewport_id or '<unknown>'} has no current screenshot")
            continue
        screenshot = ensure_within(root, screenshot_value)
        if screenshot != candidate_root and candidate_root not in screenshot.parents:
            blockers.append(f"candidate is outside the declared candidate root: {_relative(root, screenshot)}")
            continue
        if not viewport_id:
            viewport_id = screenshot.parent.name
        if viewport_id in candidates:
            blockers.append(f"duplicate candidate viewport: {viewport_id}")
            continue
        if not screenshot.is_file():
            blockers.append(f"candidate screenshot missing: {_relative(root, screenshot)}")
            continue
        candidates[viewport_id] = {
            "path": _relative(root, screenshot),
            "sha256": sha256_file(screenshot),
        }
    if len(candidates) < required_viewports:
        blockers.append(f"candidate coverage requires {required_viewports} viewports; found {len(candidates)}")
    return candidates, blockers


def _safe_within(root: Path, candidate: str | Path, label: str, errors: list[str]) -> Path | None:
    try:
        return ensure_within(root, candidate)
    except ValueError as error:
        errors.append(f"{label}: {error}")
        return None


def _review_request_id(
    scenario_id: str,
    source_revision: dict[str, Any],
    candidates: dict[str, dict[str, str]],
) -> str:
    identity = {
        "scenarioId": scenario_id,
        "sourceRevision": source_revision,
        "candidates": candidates,
    }
    return "BR-" + hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16].upper()
