"""Proposal-only structural escalation for governed AgentFlow runs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .agentflow_contracts import canonical_governed_handoff_sha256, canonical_json_sha256, validate_governed_handoff


def create_escalation_proposal(
    receipt: dict[str, Any],
    handoff: dict[str, Any],
    *,
    alternatives: list[dict[str, Any]],
) -> dict[str, Any]:
    errors = validate_governed_handoff(handoff)
    if errors:
        raise ValueError(f"invalid governed handoff: {'; '.join(errors)}")
    handoff_hash = canonical_governed_handoff_sha256(handoff)
    reference = receipt.get("handoff") if isinstance(receipt.get("handoff"), dict) else {}
    if reference.get("id") != handoff.get("handoffId") or reference.get("sha256") != handoff_hash:
        raise ValueError("receipt is not bound to the governed handoff")
    normalized_alternatives = [_alternative(item) for item in alternatives]
    if len(normalized_alternatives) < 2 or len({item["id"] for item in normalized_alternatives}) != len(normalized_alternatives):
        raise ValueError("structural escalation requires at least two uniquely identified alternatives")
    structural = _latest_structural_decision(receipt)
    proposal = {
        "schema": "proofloom/structural-escalation-proposal@1",
        "status": "REVIEW_REQUIRED",
        "mayExecute": False,
        "sourceHandoff": {"id": handoff["handoffId"], "sha256": handoff_hash},
        "sourceBuildId": (receipt.get("build") or {}).get("id"),
        "trigger": structural,
        "alternatives": normalized_alternatives,
        "requiredAuthority": "HUMAN_OR_REPOSITORY",
    }
    return {**proposal, "proposalSha256": canonical_json_sha256(proposal)}


def record_escalation_resolution(proposal: dict[str, Any], resolution: dict[str, Any]) -> dict[str, Any]:
    proposal_hash = proposal.get("proposalSha256")
    proposal_payload = {key: value for key, value in proposal.items() if key != "proposalSha256"}
    if not _hex(proposal_hash, 64) or canonical_json_sha256(proposal_payload) != proposal_hash:
        raise ValueError("escalation proposal binding is invalid")
    status = resolution.get("status")
    if status not in {"APPROVED", "REJECTED", "REVISION_REQUESTED", "CANCELLED"}:
        raise ValueError("unsupported escalation resolution")
    if resolution.get("authorityClass") != "HUMAN_OR_REPOSITORY":
        raise ValueError("approval and rejection require human or repository authority")
    record: dict[str, Any] = {
        "schema": "proofloom/structural-escalation-resolution@1",
        "proposalSha256": proposal_hash,
        "status": status,
        "authorityClass": resolution["authorityClass"],
        "recordedAt": resolution.get("recordedAt"),
        "previousRecordHash": resolution.get("previousRecordHash"),
        "reason": resolution.get("reason"),
        "mayExecute": False,
    }
    if status == "APPROVED":
        selected_id = resolution.get("selectedAlternativeId")
        if selected_id not in {item.get("id") for item in proposal.get("alternatives", []) if isinstance(item, dict)}:
            raise ValueError("approved resolution must select a proposed alternative")
        replacement = resolution.get("newHandoff")
        errors = validate_governed_handoff(replacement)
        if errors:
            raise ValueError(f"approved resolution requires a valid approved superseding handoff: {'; '.join(errors)}")
        if replacement.get("handoffId") == proposal["sourceHandoff"]["id"]:
            raise ValueError("supersession must issue a new handoff identity")
        record.update(
            {
                "selectedAlternativeId": selected_id,
                "newHandoff": deepcopy(replacement),
                "supersession": {
                    "priorHandoffId": proposal["sourceHandoff"]["id"],
                    "priorHandoffSha256": proposal["sourceHandoff"]["sha256"],
                    "newHandoffId": replacement["handoffId"],
                    "newHandoffSha256": canonical_governed_handoff_sha256(replacement),
                    "authorityEffect": "HUMAN_APPROVED_REPLACEMENT",
                },
                "mayExecute": True,
            }
        )
    return {**record, "recordHash": canonical_json_sha256(record)}


def _latest_structural_decision(receipt: dict[str, Any]) -> dict[str, Any]:
    evidence = receipt.get("evidence") if isinstance(receipt.get("evidence"), dict) else {}
    events = evidence.get("events") if isinstance(evidence.get("events"), list) else []
    for event in reversed(events):
        if not isinstance(event, dict) or event.get("type") != "governor.decision":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else event
        record = payload.get("record") if isinstance(payload.get("record"), dict) else payload
        decision = record.get("decision") if isinstance(record.get("decision"), dict) else {}
        if decision.get("action") not in {"REQUEST_RECONSIDER", "PROPOSE_REPLAN"}:
            continue
        if decision.get("authorityEffect") != "PROPOSAL_ONLY" or decision.get("requiresApproval") is not True:
            raise ValueError("structural decision attempted to self-authorize")
        record_hash = record.get("recordHash")
        record_payload = {key: value for key, value in record.items() if key not in {"recordHash", "authorityObservation"}}
        if not _hex(record_hash, 64) or canonical_json_sha256(record_payload) != record_hash:
            raise ValueError("structural decision has no durable record binding")
        return {
            "decisionRecordHash": record["recordHash"],
            "action": decision["action"],
            "ruleId": decision.get("ruleId"),
            "signals": deepcopy(decision.get("signals", {})),
        }
    raise ValueError("receipt contains no proposal-only structural decision")


def _alternative(value: dict[str, Any]) -> dict[str, str]:
    identifier = value.get("id")
    summary = value.get("summary")
    if not isinstance(identifier, str) or not identifier.strip() or not isinstance(summary, str) or not summary.strip():
        raise ValueError("every structural alternative requires an id and summary")
    return {"id": identifier.strip(), "summary": summary.strip()}


def _hex(value: Any, length: int) -> bool:
    return isinstance(value, str) and len(value) == length and all(character in "0123456789abcdef" for character in value)
