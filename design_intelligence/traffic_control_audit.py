"""Independent audit of governed AgentFlow completion receipts.

This module verifies local execution and integration evidence only. It does not
promote a receipt into deployment, production, customer-access, or outcome
proof.
"""

from __future__ import annotations

from typing import Any

from .agentflow_contracts import (
    canonical_json_sha256,
    canonical_governed_handoff_sha256,
    validate_agentflow_build_receipt,
    validate_governed_handoff,
)


def audit_traffic_control_receipt(receipt: Any, handoff: Any) -> dict[str, Any]:
    """Verify task, commit, validation, evidence, authority, and Governor proof."""
    errors = [*validate_governed_handoff(handoff), *validate_agentflow_build_receipt(receipt)]
    if not isinstance(receipt, dict) or not isinstance(handoff, dict):
        return _result(errors or ["receipt and handoff must be objects"])

    handoff_hash = canonical_governed_handoff_sha256(handoff)
    reference = receipt.get("handoff") if isinstance(receipt.get("handoff"), dict) else {}
    if reference.get("id") != handoff.get("handoffId"):
        errors.append("receipt handoff id does not match the governed handoff")
    if reference.get("sha256") != handoff_hash:
        errors.append("receipt handoff sha256 does not match the governed handoff")
    if receipt.get("proofBoundary") != _mapping(handoff.get("proof")).get("claimBoundary"):
        errors.append("receipt proof boundary does not match the governed handoff")

    build = _mapping(receipt.get("build"))
    repository = _mapping(handoff.get("repository"))
    if build.get("governedBaseCommit") != repository.get("baseCommit"):
        errors.append("receipt governed base commit does not match the handoff")
    for field in ("baseCommit", "integrationCommit"):
        if not _hex(build.get(field), 40):
            errors.append(f"receipt build.{field} must be a 40-character lowercase Git SHA")

    governed_tasks = {
        task.get("id"): task
        for task in handoff.get("tasks", [])
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    }
    receipt_tasks = {
        task.get("id"): task
        for task in receipt.get("tasks", [])
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    }
    if set(receipt_tasks) != set(governed_tasks):
        errors.append("receipt task set does not exactly match the governed handoff")
    for task_id, governed in governed_tasks.items():
        task = receipt_tasks.get(task_id)
        if task is None:
            continue
        if task.get("status") != "integrated":
            errors.append(f"task {task_id} is not integrated")
        result_commit = task.get("resultCommit")
        integration_commit = task.get("integrationCommit")
        if not _hex(result_commit, 40) or not _hex(integration_commit, 40):
            errors.append(f"task {task_id} is missing exact result and integration commits")
        elif result_commit == integration_commit:
            errors.append(f"task {task_id} result and integration commits are not independently identified")
        owns = governed.get("owns") if isinstance(governed.get("owns"), list) else []
        changed_files = task.get("changedFiles") if isinstance(task.get("changedFiles"), list) else []
        for changed_path in changed_files:
            if not isinstance(changed_path, str) or not _path_allowed(changed_path, owns):
                errors.append(f"task {task_id} changed file {changed_path!r} outside governed ownership")
        validations = task.get("validation") if isinstance(task.get("validation"), list) else []
        passed_commands = {
            item.get("command")
            for item in validations
            if isinstance(item, dict) and item.get("status") == "passed" and item.get("exitCode") == 0
        }
        for command in governed.get("validate", []):
            if command not in passed_commands:
                errors.append(f"task {task_id} validation did not pass governed command {command!r}")

    evidence = _mapping(receipt.get("evidence"))
    events = evidence.get("events") if isinstance(evidence.get("events"), list) else []
    satisfied = {
        requirement
        for event in events
        if isinstance(event, dict) and event.get("type") == "evidence.recorded"
        for requirement in _string_list(_mapping(event.get("payload")).get("satisfied"))
    }
    required = set(_string_list(_mapping(handoff.get("proof")).get("requiredEvidence")))
    missing = sorted(required - satisfied)
    if missing:
        errors.append(f"receipt is missing required evidence: {', '.join(missing)}")

    governor_errors = _audit_governor_events(events, handoff, handoff_hash)
    errors.extend(governor_errors)
    complete = (
        build.get("status") == "completed"
        and bool(receipt_tasks)
        and all(task.get("status") == "integrated" for task in receipt_tasks.values())
    )
    return _result(
        errors,
        execution_complete=complete and not errors,
        governor_verified=not governor_errors,
        proof_boundary=receipt.get("proofBoundary"),
    )


def _audit_governor_events(events: list[Any], handoff: dict[str, Any], handoff_hash: str) -> list[str]:
    errors: list[str] = []
    governor_events = [event for event in events if isinstance(event, dict) and event.get("type") == "governor.decision"]
    if not governor_events:
        return ["receipt contains no Governor decision provenance"]
    previous: str | None = None
    final_action: Any = None
    for index, event in enumerate(governor_events):
        wrapper = _mapping(event.get("payload"))
        record = _mapping(wrapper.get("record")) or wrapper
        record_hash = record.get("recordHash")
        hash_payload = {
            key: value
            for key, value in record.items()
            if key not in {"recordHash", "authorityObservation"}
        }
        if not _hex(record_hash, 64) or canonical_json_sha256(hash_payload) != record_hash:
            errors.append(f"Governor decision record hash is invalid at index {index}")
        if record.get("previousRecordHash") != previous:
            errors.append(f"Governor decision record chain is invalid at index {index}")
        if record.get("contractHash") != handoff_hash:
            errors.append(f"Governor decision record contract hash differs at index {index}")
        if record.get("policyVersion") != "governor.v1":
            errors.append(f"Governor policy version is unsupported at index {index}")
        decision = _mapping(record.get("decision"))
        if decision.get("policyVersion") != record.get("policyVersion"):
            errors.append(f"Governor decision policy provenance differs at index {index}")
        final_action = decision.get("action")
        previous = record_hash if isinstance(record_hash, str) else None
        authority = _mapping(wrapper.get("authorityObservation")) or _mapping(record.get("authorityObservation"))
        errors.extend(_authority_errors(authority, handoff, handoff_hash, index))
    if final_action != "CONTINUE":
        errors.append("final Governor decision must be CONTINUE before completion")
    return errors


def _authority_errors(authority: dict[str, Any], handoff: dict[str, Any], handoff_hash: str, index: int) -> list[str]:
    repository = _mapping(handoff.get("repository"))
    governed_authority = _mapping(handoff.get("authority"))
    comparisons = {
        "approval authority": (authority.get("approvalAuthority"), "HUMAN_OR_REPOSITORY"),
        "handoff id": (authority.get("handoffId"), handoff.get("handoffId")),
        "handoff digest": (authority.get("handoffSha256"), handoff_hash),
        "base commit": (authority.get("baseCommit"), repository.get("baseCommit")),
        "snapshot digest": (authority.get("snapshotSha256"), repository.get("snapshotSha256")),
        "worktree state": (authority.get("worktreeState"), "clean"),
        "authority state": (authority.get("authorityStateSha256"), governed_authority.get("stateSha256")),
        "governance report": (authority.get("governanceReportSha256"), governed_authority.get("governanceReportSha256")),
    }
    errors = [f"Governor authority {label} differs at index {index}" for label, (actual, expected) in comparisons.items() if actual != expected]
    if canonical_json_sha256(authority.get("authoritySources")) != canonical_json_sha256(governed_authority.get("sources")):
        errors.append(f"Governor authority source digests differ at index {index}")
    return errors


def _result(errors: list[str], *, execution_complete: bool = False, governor_verified: bool = False, proof_boundary: Any = None) -> dict[str, Any]:
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "executionComplete": execution_complete,
        "governorVerified": governor_verified,
        "proofBoundary": proof_boundary,
        "claim": "AgentFlow local execution and integration evidence verified." if not errors and execution_complete else "No completed execution claim is available.",
    }


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _hex(value: Any, length: int) -> bool:
    return isinstance(value, str) and len(value) == length and all(character in "0123456789abcdef" for character in value)


def _path_allowed(candidate: str, roots: list[Any]) -> bool:
    normalized = candidate.replace("\\", "/").removeprefix("./")
    for root in roots:
        if not isinstance(root, str):
            continue
        prefix = root.replace("\\", "/").removeprefix("./").rstrip("/")
        if normalized == prefix or normalized.startswith(f"{prefix}/"):
            return True
    return False
