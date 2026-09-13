from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .memory import MEMORY_FILES, append_decision, append_outcome, memory_root
from .storage import atomic_write_json, ensure_within, read_json, read_jsonl, sha256_file


RATIFICATION_DECISIONS = {"PROMOTE", "REJECT"}
MAX_RECEIPT_AGE_DAYS = 7


def create_outcome_ratification_receipt(
    repository_root: str | Path,
    assessment_path: str | Path,
    decision: dict[str, Any],
    output_path: str | Path,
    *,
    decided_at: datetime | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    source = ensure_within(root, assessment_path)
    destination = ensure_within(root, output_path)
    if destination.exists():
        raise ValueError(f"Outcome ratification receipts are append-only: {_relative(root, destination)} already exists")
    assessment = read_json(source, {}) or {}
    errors = _assessment_errors(assessment)
    candidate_decision_id = (assessment.get("memoryCandidate") or {}).get("decisionId")
    if candidate_decision_id and not _decision_exists(root, candidate_decision_id):
        errors.append(f"assessment decision not found: {candidate_decision_id}")
    action = str(decision.get("decision", "")).upper()
    authorized_by = str(decision.get("authorizedBy", "")).strip()
    reason = str(decision.get("reason", "")).strip()
    if action not in RATIFICATION_DECISIONS:
        errors.append("decision.decision must be PROMOTE or REJECT")
    if not _is_human(authorized_by):
        errors.append("decision.authorizedBy requires explicit human authority")
    if not reason:
        errors.append("decision.reason is required")
    outcome_id = str(decision.get("outcomeId", "")).strip()
    if action == "PROMOTE" and not outcome_id.startswith("DO-"):
        errors.append("decision.outcomeId must start with DO- for PROMOTE")
    if errors:
        raise ValueError("Outcome ratification denied: " + "; ".join(errors))

    decided = _aware(decided_at or datetime.now(timezone.utc), "decided_at")
    candidate = assessment["memoryCandidate"]
    receipt: dict[str, Any] = {
        "schemaVersion": 1,
        "kind": "design-intelligence/outcome-ratification-receipt",
        "assessmentEvidence": {"path": _relative(root, source), "sha256": sha256_file(source)},
        "contractId": assessment["contractId"],
        "decisionId": candidate["decisionId"],
        "decision": action,
        "authorizedBy": authorized_by,
        "reason": reason,
        "decidedAt": _iso(decided),
        "validUntil": _iso(decided + timedelta(days=MAX_RECEIPT_AGE_DAYS)),
        "outcomeId": outcome_id or None,
        "lesson": str(decision.get("lesson", "")).strip() or candidate["lesson"],
        "memoryMutationPerformed": False,
    }
    receipt["id"] = "DOR-" + _digest(receipt)[:20].upper()
    atomic_write_json(destination, receipt)
    return receipt


def audit_outcome_ratification_receipt(
    repository_root: str | Path,
    receipt_path: str | Path,
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    source = ensure_within(root, receipt_path)
    receipt = read_json(source, {}) or {}
    errors: list[str] = []
    for field in ("id", "kind", "assessmentEvidence", "contractId", "decisionId", "decision", "authorizedBy", "reason", "decidedAt", "validUntil"):
        if receipt.get(field) in (None, "", [], {}):
            errors.append(f"receipt.{field} is required")
    if receipt.get("kind") != "design-intelligence/outcome-ratification-receipt":
        errors.append("receipt.kind is invalid")
    if receipt.get("decision") not in RATIFICATION_DECISIONS:
        errors.append("receipt.decision is invalid")
    if receipt.get("decision") == "PROMOTE" and not str(receipt.get("outcomeId", "")).startswith("DO-"):
        errors.append("receipt.outcomeId must start with DO- for PROMOTE")
    if not _is_human(receipt.get("authorizedBy")):
        errors.append("receipt.authorizedBy requires explicit human authority")
    if receipt.get("memoryMutationPerformed") is not False:
        errors.append("receipt.memoryMutationPerformed must be false")
    expected_id = "DOR-" + _digest({key: value for key, value in receipt.items() if key != "id"})[:20].upper()
    if receipt.get("id") != expected_id:
        errors.append("receipt.id does not match canonical receipt content")

    binding = receipt.get("assessmentEvidence") or {}
    assessment: dict[str, Any] = {}
    try:
        assessment_path = ensure_within(root, binding.get("path", ""))
        if not assessment_path.is_file():
            errors.append("receipt.assessmentEvidence path is missing")
        elif sha256_file(assessment_path) != binding.get("sha256"):
            errors.append("receipt.assessmentEvidence hash mismatch")
        else:
            assessment = read_json(assessment_path, {}) or {}
            errors.extend(f"assessment: {error}" for error in _assessment_errors(assessment))
    except (TypeError, ValueError):
        errors.append("receipt.assessmentEvidence path is invalid")
    if assessment:
        candidate = assessment.get("memoryCandidate") or {}
        if assessment.get("contractId") != receipt.get("contractId"):
            errors.append("receipt.contractId does not match bound assessment")
        if candidate.get("decisionId") != receipt.get("decisionId"):
            errors.append("receipt.decisionId does not match bound assessment")
        if candidate.get("decisionId") and not _decision_exists(root, candidate["decisionId"]):
            errors.append(f"assessment decision not found: {candidate['decisionId']}")

    now = _aware(as_of or datetime.now(timezone.utc), "as_of")
    decided = _parse(receipt.get("decidedAt"), "receipt.decidedAt", errors)
    valid_until = _parse(receipt.get("validUntil"), "receipt.validUntil", errors)
    if decided and valid_until:
        duration = valid_until - decided
        if duration <= timedelta(0) or duration > timedelta(days=MAX_RECEIPT_AGE_DAYS):
            errors.append(f"receipt validity cannot exceed {MAX_RECEIPT_AGE_DAYS} days")
        if now > valid_until:
            errors.append("receipt has expired")
        if now < decided:
            errors.append("receipt decision is in the future")
    return {
        "status": "PASS" if not errors else "FAIL",
        "receiptId": receipt.get("id"),
        "decision": receipt.get("decision"),
        "errors": errors,
        "memoryMutationPerformed": False,
    }


def promote_outcome_from_receipt(
    repository_root: str | Path,
    receipt_path: str | Path,
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    source = ensure_within(root, receipt_path)
    audit = audit_outcome_ratification_receipt(root, source, as_of=as_of)
    if audit["status"] != "PASS":
        raise ValueError("Outcome promotion denied: " + "; ".join(audit["errors"]))
    receipt = read_json(source, {}) or {}
    if receipt["decision"] != "PROMOTE":
        raise ValueError("Outcome promotion denied: receipt decision is not PROMOTE")
    assessment = read_json(ensure_within(root, receipt["assessmentEvidence"]["path"]), {}) or {}
    candidate = assessment["memoryCandidate"]
    outcome = {
        "id": receipt["outcomeId"],
        "decisionId": receipt["decisionId"],
        "result": "accepted",
        "reason": candidate["reason"],
        "evidence": candidate["sourceEvidence"],
        "lesson": receipt["lesson"],
        "product": candidate.get("product"),
        "surface": candidate.get("surface"),
        "component": candidate.get("component"),
        "recordedAt": _iso(_aware(as_of or datetime.now(timezone.utc), "as_of")),
        "ratification": {
            "receiptId": receipt["id"],
            "receiptPath": _relative(root, source),
            "receiptSha256": sha256_file(source),
            "authorizedBy": receipt["authorizedBy"],
        },
    }
    append_outcome(root, outcome)
    return {"status": "PROMOTED", "outcome": outcome, "canonicalMemoryPath": ".design/memory/outcomes.jsonl", "receiptMutationPerformed": False}


def retire_promoted_decision(
    repository_root: str | Path,
    retirement: dict[str, Any],
    *,
    retired_at: datetime | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    decision_id = str(retirement.get("decisionId", "")).strip()
    authorized_by = str(retirement.get("authorizedBy", "")).strip()
    reason = str(retirement.get("reason", "")).strip()
    errors: list[str] = []
    if not decision_id.startswith("DL-"):
        errors.append("retirement.decisionId must start with DL-")
    if not _is_human(authorized_by):
        errors.append("retirement.authorizedBy requires explicit human authority")
    if not reason:
        errors.append("retirement.reason is required")
    records = read_jsonl(memory_root(root) / MEMORY_FILES["decisions"])
    matching = [item for item in records if item.get("id") == decision_id]
    latest = max(matching, key=lambda item: int(item.get("revision", 1)), default=None)
    if latest is None:
        errors.append(f"decision not found: {decision_id}")
    elif latest.get("status") != "accepted":
        errors.append("only an accepted decision can be retired")
    if errors:
        raise ValueError("Outcome retirement denied: " + "; ".join(errors))
    assert latest is not None
    retired = dict(latest)
    retired.update({
        "status": "deprecated",
        "revision": int(latest.get("revision", 1)) + 1,
        "createdAt": _iso(_aware(retired_at or datetime.now(timezone.utc), "retired_at")),
        "reason": reason,
        "retirement": {"authorizedBy": authorized_by, "reason": reason},
    })
    append_decision(root, retired)
    return {"status": "RETIRED", "decision": retired, "canonicalMemoryPath": ".design/memory/decisions.jsonl", "historyPreserved": True}


def _assessment_errors(assessment: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    candidate = assessment.get("memoryCandidate") or {}
    if assessment.get("kind") != "design-intelligence/outcome-assessment":
        errors.append("assessment.kind is invalid")
    if assessment.get("status") != "PASS" or assessment.get("outcomeStatus") != "SUCCESS":
        errors.append("assessment must be a completed SUCCESS")
    if candidate.get("eligible") is not True or candidate.get("ratificationStatus") != "HUMAN_REQUIRED":
        errors.append("assessment memory candidate is not eligible for human ratification")
    if not str(candidate.get("decisionId", "")).startswith("DL-"):
        errors.append("assessment memory candidate requires a DL- decisionId")
    if not candidate.get("sourceEvidence"):
        errors.append("assessment memory candidate requires source evidence")
    return errors


def _decision_exists(root: Path, decision_id: str) -> bool:
    return any(
        item.get("id") == decision_id
        for item in read_jsonl(memory_root(root) / MEMORY_FILES["decisions"])
    )


def _is_human(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower().startswith("human:") and len(value.strip()) > 6


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse(value: Any, label: str, errors: list[str]) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return _aware(parsed, label)
    except (TypeError, ValueError):
        errors.append(f"{label} must be a timezone-aware ISO-8601 datetime")
        return None


def _aware(value: datetime, label: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _relative(root: Path, target: Path) -> str:
    return target.resolve().relative_to(root).as_posix()
