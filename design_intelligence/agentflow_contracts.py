from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any


HANDOFF_KIND = "design-intelligence/governed-task-handoff"
RECEIPT_KIND = "agentflow/build-receipt"
SCHEMA_VERSION = "1.0.0"


def canonical_json_sha256(document: dict[str, Any]) -> str:
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_governed_handoff(document: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(document)
    tasks = normalized.get("tasks")
    if isinstance(tasks, list):
        for task in tasks:
            if isinstance(task, dict):
                task.setdefault("produces", [])
                task.setdefault("consumes", [])
    return normalized


def canonical_governed_handoff_sha256(document: dict[str, Any]) -> str:
    return canonical_json_sha256(_normalize_governed_handoff(document))


def load_governed_handoff(path: str | Path, *, require_approved: bool = True) -> dict[str, Any]:
    document = _load_json(path)
    errors = validate_governed_handoff(document, require_approved=require_approved)
    if errors:
        raise ValueError("Invalid governed task handoff: " + "; ".join(errors))
    return document


def write_governed_handoff(source: dict[str, Any], path: str | Path) -> dict[str, Any]:
    normalized = _normalize_governed_handoff(source)
    errors = validate_governed_handoff(normalized, require_approved=False)
    if errors:
        raise ValueError("Invalid governed task handoff: " + "; ".join(errors))
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(normalized, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "status": "PASS",
        "output": str(output.resolve()),
        "handoffId": normalized["handoffId"],
        "authorityStatus": normalized["authority"]["status"],
        "sha256": canonical_governed_handoff_sha256(normalized),
        "executionAuthorized": normalized["authority"]["status"] == "APPROVED",
    }


def audit_agentflow_build_receipt(
    path: str | Path,
    *,
    handoff_path: str | Path | None = None,
) -> dict[str, Any]:
    receipt = _load_json(path)
    errors = validate_agentflow_build_receipt(receipt)
    handoff = None
    if handoff_path is not None:
        handoff = load_governed_handoff(handoff_path)
        expected = canonical_governed_handoff_sha256(handoff)
        legacy_expected = canonical_json_sha256(handoff)
        reference = receipt.get("handoff", {})
        if reference.get("id") != handoff.get("handoffId"):
            errors.append("receipt handoff id does not match the governed handoff")
        if reference.get("sha256") not in {expected, legacy_expected}:
            errors.append("receipt handoff sha256 does not match the governed handoff")
    build = receipt.get("build", {})
    task_states = [task.get("status") for task in receipt.get("tasks", []) if isinstance(task, dict)]
    complete = build.get("status") == "completed" and task_states and all(state == "integrated" for state in task_states)
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "handoffVerified": handoff is not None and not any("handoff" in error for error in errors),
        "executionComplete": bool(complete),
        "proofBoundary": receipt.get("proofBoundary"),
        "claim": (
            "AgentFlow execution and local integration evidence verified; stronger release, production, provider, customer, and human-acceptance claims remain outside this receipt."
            if not errors and complete
            else "No completed execution claim is available."
        ),
    }


def validate_governed_handoff(document: Any, *, require_approved: bool = True) -> list[str]:
    errors = _require_mapping(document)
    if errors:
        return errors
    assert isinstance(document, dict)
    _constant(document, "schemaVersion", SCHEMA_VERSION, errors)
    _constant(document, "kind", HANDOFF_KIND, errors)
    _required_text(document, "handoffId", errors)
    _datetime_field(document, "createdAt", errors)
    _required_text(document, "objective", errors)
    repository = _mapping_field(document, "repository", errors)
    if repository is not None:
        base_commit = repository.get("baseCommit")
        if not _hex(base_commit, 40):
            errors.append("repository.baseCommit must be a 40-character lowercase Git SHA")
    authority = _mapping_field(document, "authority", errors)
    if authority is not None:
        status = authority.get("status")
        if status not in {"PROPOSED", "APPROVED"}:
            errors.append("authority.status must be PROPOSED or APPROVED")
        if require_approved and status != "APPROVED":
            errors.append("authority.status must be APPROVED for execution")
        if status == "APPROVED":
            _required_text(authority, "approvedBy", errors, prefix="authority.")
            _datetime_field(authority, "approvedAt", errors, prefix="authority.")
        sources = authority.get("sources")
        if not isinstance(sources, list) or not sources:
            errors.append("authority.sources must contain at least one source")
        else:
            for index, source in enumerate(sources):
                if not isinstance(source, dict) or not isinstance(source.get("path"), str) or not _hex(source.get("sha256"), 64):
                    errors.append(f"authority.sources[{index}] must contain path and lowercase sha256")
    tasks = document.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        errors.append("tasks must contain at least one task")
    else:
        ids = {task.get("id") for task in tasks if isinstance(task, dict)}
        for index, task in enumerate(tasks):
            if not isinstance(task, dict):
                errors.append(f"tasks[{index}] must be an object")
                continue
            for field in ("id", "title", "description"):
                _required_text(task, field, errors, prefix=f"tasks[{index}].")
            if not isinstance(task.get("estimateHours"), (int, float)) or task.get("estimateHours", 0) <= 0:
                errors.append(f"tasks[{index}].estimateHours must be positive")
            for field in ("owns", "acceptanceCriteria", "validate"):
                if not _nonempty_text_list(task.get(field)):
                    errors.append(f"tasks[{index}].{field} must contain at least one value")
            dependencies = task.get("dependsOn")
            if not isinstance(dependencies, list) or any(not isinstance(item, str) for item in dependencies):
                errors.append(f"tasks[{index}].dependsOn must be a string array")
            else:
                for dependency in dependencies:
                    if dependency not in ids:
                        errors.append(f"tasks[{index}] references missing dependency {dependency}")
                    if dependency == task.get("id"):
                        errors.append(f"tasks[{index}] cannot depend on itself")
        if len(ids) != len(tasks):
            errors.append("task ids must be unique")
    proof = _mapping_field(document, "proof", errors)
    if proof is not None:
        if not _nonempty_text_list(proof.get("requiredEvidence")):
            errors.append("proof.requiredEvidence must contain at least one value")
        _required_text(proof, "claimBoundary", errors, prefix="proof.")
    return errors


def validate_agentflow_build_receipt(document: Any) -> list[str]:
    errors = _require_mapping(document)
    if errors:
        return errors
    assert isinstance(document, dict)
    _constant(document, "schemaVersion", SCHEMA_VERSION, errors)
    _constant(document, "kind", RECEIPT_KIND, errors)
    handoff = _mapping_field(document, "handoff", errors)
    if handoff is not None:
        _required_text(handoff, "id", errors, prefix="handoff.")
        if not _hex(handoff.get("sha256"), 64):
            errors.append("handoff.sha256 must be a 64-character lowercase digest")
    build = _mapping_field(document, "build", errors)
    if build is not None:
        _required_text(build, "id", errors, prefix="build.")
        _required_text(build, "status", errors, prefix="build.")
        if not _hex(build.get("baseCommit"), 40):
            errors.append("build.baseCommit must be a 40-character lowercase Git SHA")
    if not isinstance(document.get("tasks"), list):
        errors.append("tasks must be an array")
    evidence = _mapping_field(document, "evidence", errors)
    if evidence is not None:
        for field in ("events", "artifacts", "approvals"):
            if not isinstance(evidence.get(field), list):
                errors.append(f"evidence.{field} must be an array")
    _required_text(document, "proofBoundary", errors)
    _datetime_field(document, "generatedAt", errors)
    return errors


def _load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON document must be an object")
    return value


def _require_mapping(value: Any) -> list[str]:
    return [] if isinstance(value, dict) else ["document must be an object"]


def _mapping_field(document: dict[str, Any], field: str, errors: list[str]) -> dict[str, Any] | None:
    value = document.get(field)
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return None
    return value


def _constant(document: dict[str, Any], field: str, expected: str, errors: list[str]) -> None:
    if document.get(field) != expected:
        errors.append(f"{field} must equal {expected}")


def _required_text(document: dict[str, Any], field: str, errors: list[str], *, prefix: str = "") -> None:
    if not isinstance(document.get(field), str) or not document[field].strip():
        errors.append(f"{prefix}{field} must be non-empty text")


def _datetime_field(document: dict[str, Any], field: str, errors: list[str], *, prefix: str = "") -> None:
    value = document.get(field)
    try:
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{prefix}{field} must be an ISO-8601 datetime")


def _hex(value: Any, length: int) -> bool:
    return isinstance(value, str) and len(value) == length and all(character in "0123456789abcdef" for character in value)


def _nonempty_text_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and bool(item.strip()) for item in value)
