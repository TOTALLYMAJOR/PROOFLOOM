from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any

from .baselines import audit_baseline_review_request
from .memory import memory_root
from .storage import atomic_write_json, ensure_within, read_json, read_jsonl, sha256_file


RECEIPT_DECISIONS = {"APPROVE", "REJECT", "DEFER"}
MAX_APPROVAL_AGE_DAYS = 7
MAX_DEFER_AGE_DAYS = 30
MAX_REQUEST_AGE_DAYS = 14


def load_review_policy(
    repository_root: str | Path,
    policy_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    source = (
        ensure_within(root, policy_path)
        if policy_path
        else root / ".design/baselines/review-policy.json"
    )
    if source.is_file():
        policy = read_json(source, {}) or {}
    else:
        default = files("design_intelligence").joinpath(
            "data/defaults/baseline-review-policy.json"
        )
        policy = json.loads(default.read_text(encoding="utf-8"))
    errors = audit_review_policy(policy)
    if errors:
        raise ValueError(
            "Review policy weakens protected governance: " + "; ".join(errors)
        )
    return policy


def audit_review_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if policy.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    for field, maximum in (
        ("maxRequestAgeDays", MAX_REQUEST_AGE_DAYS),
        ("maxApprovalAgeDays", MAX_APPROVAL_AGE_DAYS),
        ("maxDeferAgeDays", MAX_DEFER_AGE_DAYS),
    ):
        value = policy.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            errors.append(f"{field} must be a positive integer")
        elif value > maximum:
            errors.append(f"{field} cannot exceed {maximum}")
    for field in (
        "requireHumanAuthority",
        "requireBoundVisualAcceptance",
        "requireBoundSemanticAccessibility",
    ):
        if policy.get(field) is not True:
            errors.append(f"{field} must remain true")
    return errors


def create_baseline_review_receipt(
    repository_root: str | Path,
    request_path: str | Path,
    decision: dict[str, Any],
    output_path: str | Path,
    *,
    decided_at: datetime | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    request_source = ensure_within(root, request_path)
    destination = ensure_within(root, output_path)
    if destination.exists():
        raise ValueError(f"Review receipts are append-only: {_relative(root, destination)} already exists")

    request_audit = audit_baseline_review_request(root, request_source)
    if request_audit.get("status") != "PASS":
        raise ValueError("Review receipt denied: request integrity audit failed")
    decided = decided_at or datetime.now(timezone.utc)
    if decided.tzinfo is None:
        raise ValueError("Review receipt denied: decided_at must be timezone-aware")
    decided = decided.astimezone(timezone.utc)
    policy = load_review_policy(root)
    request = read_json(request_source, {}) or {}
    errors = _validate_decision_input(
        root,
        request,
        decision,
        decided,
        destination.parent,
        int(policy["maxRequestAgeDays"]),
        int(policy["maxApprovalAgeDays"]),
        int(policy["maxDeferAgeDays"]),
    )
    if errors:
        raise ValueError("Review receipt denied: " + "; ".join(errors))

    receipt = {
        "schemaVersion": 1,
        "requestId": request["id"],
        "requestEvidence": {
            "path": _relative(root, request_source),
            "sha256": sha256_file(request_source),
        },
        "decision": decision["decision"],
        "authorizedBy": decision["authorizedBy"],
        "reason": decision["reason"],
        "decidedAt": _iso(decided),
        "supersedes": decision.get("supersedes"),
        "baselineMutationPerformed": False,
        "promotionPerformed": False,
    }
    if decision["decision"] == "APPROVE":
        valid_days = int(decision.get("validForDays", policy["maxApprovalAgeDays"]))
        receipt.update({
            "decisionMemoryId": decision["decisionMemoryId"],
            "validUntil": _iso(decided + timedelta(days=valid_days)),
            "visualAcceptanceEvidence": _bind_human_evidence(
                root,
                decision["visualAcceptanceEvidence"],
                request["id"],
                "visual-acceptance",
                decided,
            ),
            "semanticAccessibilityEvidence": _bind_human_evidence(
                root,
                decision["semanticAccessibilityEvidence"],
                request["id"],
                "semantic-accessibility",
                decided,
            ),
        })
    elif decision["decision"] == "DEFER":
        review_after = datetime.fromisoformat(decision["reviewAfter"].replace("Z", "+00:00"))
        receipt["reviewAfter"] = _iso(review_after)
    receipt["id"] = _receipt_id(receipt)
    atomic_write_json(destination, receipt)
    return receipt


def audit_baseline_review_receipt(
    repository_root: str | Path,
    receipt_path: str | Path,
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    source = ensure_within(root, receipt_path)
    receipt = read_json(source, {}) or {}
    policy = load_review_policy(root)
    errors: list[str] = []
    required = (
        "id",
        "requestId",
        "requestEvidence",
        "decision",
        "authorizedBy",
        "reason",
        "decidedAt",
    )
    errors.extend(
        f"receipt.{field} is required"
        for field in required
        if receipt.get(field) in (None, "", [], {})
    )
    if receipt.get("baselineMutationPerformed") is not False:
        errors.append("receipt.baselineMutationPerformed must be false")
    if receipt.get("promotionPerformed") is not False:
        errors.append("receipt.promotionPerformed must be false")
    if receipt.get("decision") not in RECEIPT_DECISIONS:
        errors.append("receipt.decision is invalid")
    if not _is_human(receipt.get("authorizedBy")):
        errors.append("receipt.authorizedBy requires explicit human authority")

    request_entry = receipt.get("requestEvidence") or {}
    request_path = _audit_file_binding(root, "requestEvidence", request_entry, errors)
    request: dict[str, Any] = {}
    if request_path:
        request = read_json(request_path, {}) or {}
        request_audit = audit_baseline_review_request(root, request_path)
        errors.extend(f"request: {error}" for error in request_audit.get("errors", []))
        if request.get("id") != receipt.get("requestId"):
            errors.append("receipt.requestId does not match bound request")
        if receipt.get("decision") == "APPROVE" and request.get("status") != "REVIEWABLE":
            errors.append("APPROVE requires a REVIEWABLE request")

    decided = _parse_datetime(receipt.get("decidedAt"), "receipt.decidedAt", errors)
    valid_until: datetime | None = None
    review_after: datetime | None = None
    if receipt.get("decision") == "APPROVE":
        for field in (
            "decisionMemoryId",
            "validUntil",
            "visualAcceptanceEvidence",
            "semanticAccessibilityEvidence",
        ):
            if receipt.get(field) in (None, "", [], {}):
                errors.append(f"receipt.{field} is required for APPROVE")
        valid_until = _parse_datetime(receipt.get("validUntil"), "receipt.validUntil", errors)
        if decided and valid_until:
            validity = valid_until - decided
            if validity <= timedelta(0) or validity > timedelta(days=policy["maxApprovalAgeDays"]):
                errors.append(
                    "receipt validity must be between 1 second and "
                    f"{policy['maxApprovalAgeDays']} days"
                )
        if request and decided:
            _validate_request_freshness(
                request,
                decided,
                int(policy["maxRequestAgeDays"]),
                errors,
            )
        for field, scope in (
            ("visualAcceptanceEvidence", "visual-acceptance"),
            ("semanticAccessibilityEvidence", "semantic-accessibility"),
        ):
            _audit_human_evidence(
                root,
                field,
                receipt.get(field) or {},
                str(receipt.get("requestId") or ""),
                scope,
                decided,
                errors,
            )
        _validate_accepted_decision(root, receipt.get("decisionMemoryId"), errors)
    elif receipt.get("decision") == "DEFER":
        review_after = _parse_datetime(receipt.get("reviewAfter"), "receipt.reviewAfter", errors)
        if decided and review_after and review_after <= decided:
            errors.append("receipt.reviewAfter must postdate receipt.decidedAt")
        if decided and review_after and review_after - decided > timedelta(days=policy["maxDeferAgeDays"]):
            errors.append(
                f"receipt.reviewAfter cannot exceed {policy['maxDeferAgeDays']} days"
            )
    _validate_supersession(root, source.parent, receipt, decided, errors)
    if receipt.get("id") and receipt.get("id") != _receipt_id(receipt):
        errors.append("receipt.id does not match its evidence identity")

    now = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if receipt.get("decision") == "APPROVE":
        lifecycle = "EXPIRED" if valid_until and now > valid_until else "ACTIVE"
    elif receipt.get("decision") == "DEFER":
        lifecycle = "REVIEW_DUE" if review_after and now > review_after else "DEFERRED"
    else:
        lifecycle = "FINAL"
    return {
        "status": "PASS" if not errors else "FAIL",
        "receiptId": receipt.get("id"),
        "decision": receipt.get("decision"),
        "lifecycle": lifecycle,
        "checked": 3,
        "errors": errors,
    }


def preflight_baseline_promotion(
    repository_root: str | Path,
    receipt_path: str | Path,
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    source = ensure_within(root, receipt_path)
    receipt = read_json(source, {}) or {}
    audit = audit_baseline_review_receipt(root, source, as_of=as_of)
    errors = list(audit.get("errors", []))
    if receipt.get("decision") != "APPROVE":
        errors.append("promotion preflight requires an APPROVE receipt")
    if audit.get("lifecycle") != "ACTIVE":
        errors.append(f"approval receipt is {str(audit.get('lifecycle') or 'invalid').lower()}")
    superseding = _superseding_receipts(root, source.parent, receipt)
    if superseding:
        errors.append("approval receipt was superseded by " + ", ".join(superseding))

    request_entry = receipt.get("requestEvidence") or {}
    request: dict[str, Any] = {}
    try:
        request_path = ensure_within(root, request_entry.get("path", ""))
    except ValueError as error:
        errors.append(f"requestEvidence: {error}")
        request_path = None
    if request_path and request_path.is_file():
        request = read_json(request_path, {}) or {}
    elif request_path:
        errors.append("requestEvidence: file missing")
    approval = {
        "decisionId": receipt.get("decisionMemoryId"),
        "reason": receipt.get("reason"),
        "authorizedBy": receipt.get("authorizedBy"),
        "validationStatus": "PASS" if not errors else "FAIL",
        "validationEvidence": [
            _relative(root, source),
            request_entry.get("path"),
            (receipt.get("visualAcceptanceEvidence") or {}).get("path"),
            (receipt.get("semanticAccessibilityEvidence") or {}).get("path"),
        ],
        "reviewReceiptId": receipt.get("id"),
        "requestId": receipt.get("requestId"),
        "validUntil": receipt.get("validUntil"),
    }
    return {
        "status": "READY" if not errors else "BLOCKED",
        "scenarioId": request.get("scenarioId"),
        "candidateRoot": request.get("candidateRoot"),
        "approval": approval,
        "baselineMutationPerformed": False,
        "errors": errors,
    }


def evaluate_baseline_review_lifecycle(
    repository_root: str | Path,
    *,
    requests_root: str | Path = "artifacts/design/baseline-requests",
    receipts_root: str | Path = "artifacts/design/baseline-decisions",
    as_of: datetime | None = None,
    max_request_age_days: int | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    requests_path = ensure_within(root, requests_root)
    receipts_path = ensure_within(root, receipts_root)
    policy = load_review_policy(root)
    request_age_days = (
        int(policy["maxRequestAgeDays"])
        if max_request_age_days is None
        else max_request_age_days
    )
    if request_age_days < 1 or request_age_days > int(policy["maxRequestAgeDays"]):
        raise ValueError(
            "max_request_age_days must be positive and cannot weaken review policy"
        )
    now = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
    errors: list[str] = []
    request_records: list[dict[str, Any]] = []

    for path in sorted(requests_path.glob("*.json")):
        request = read_json(path, {}) or {}
        audit = audit_baseline_review_request(root, path)
        requested_at = _parse_datetime(
            request.get("requestedAt"),
            f"{path.name}.requestedAt",
            errors,
        )
        request_records.append({
            "path": path,
            "request": request,
            "audit": audit,
            "requestedAt": requested_at,
        })

    superseded_requests: set[str] = set()
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in request_records:
        request = record["request"]
        grouped.setdefault(
            (str(request.get("product")), str(request.get("scenarioId"))),
            [],
        ).append(record)
    for records in grouped.values():
        ordered = sorted(
            (record for record in records if record["requestedAt"]),
            key=lambda record: record["requestedAt"],
        )
        if len(ordered) > 1:
            superseded_requests.update(
                str(record["request"].get("id"))
                for record in ordered[:-1]
            )

    valid_receipts: list[dict[str, Any]] = []
    for path in sorted(receipts_path.glob("*.json")):
        receipt = read_json(path, {}) or {}
        audit = audit_baseline_review_receipt(root, path, as_of=now)
        if audit.get("status") != "PASS":
            errors.extend(f"{path.name}: {error}" for error in audit.get("errors", []))
            continue
        valid_receipts.append({"path": path, "receipt": receipt, "audit": audit})
    superseded_receipts = {
        str(record["receipt"].get("supersedes"))
        for record in valid_receipts
        if record["receipt"].get("supersedes")
    }

    results: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for record in request_records:
        request = record["request"]
        request_id = str(request.get("id") or "")
        current_receipts = [
            item
            for item in valid_receipts
            if item["receipt"].get("requestId") == request_id
            and item["receipt"].get("id") not in superseded_receipts
        ]
        if record["audit"].get("status") != "PASS" or not record["requestedAt"]:
            state = "INVALID"
            errors.extend(
                f"{record['path'].name}: {error}"
                for error in record["audit"].get("errors", [])
            )
        elif request_id in superseded_requests:
            state = "SUPERSEDED"
        elif len(current_receipts) > 1:
            state = "CONFLICT"
            errors.append(f"{request_id}: multiple unsuperseded decision receipts")
        elif current_receipts:
            current = current_receipts[0]
            decision = current["receipt"].get("decision")
            lifecycle = current["audit"].get("lifecycle")
            if decision == "APPROVE":
                state = "APPROVED_PENDING_PROMOTION" if lifecycle == "ACTIVE" else "APPROVAL_EXPIRED"
            elif decision == "DEFER":
                state = str(lifecycle)
            else:
                state = "REJECTED"
        elif request.get("status") == "BLOCKED":
            state = "BLOCKED"
        elif now - record["requestedAt"] > timedelta(days=request_age_days):
            state = "STALE"
        else:
            state = "REVIEWABLE"
        counts[state] = counts.get(state, 0) + 1
        results.append({
            "requestId": request_id,
            "product": request.get("product"),
            "scenarioId": request.get("scenarioId"),
            "state": state,
            "path": _relative(root, record["path"]),
        })
    return {
        "status": "PASS" if not errors else "FAIL",
        "asOf": _iso(now),
        "maxRequestAgeDays": request_age_days,
        "counts": counts,
        "requests": results,
        "errors": errors,
    }


def _validate_decision_input(
    root: Path,
    request: dict[str, Any],
    decision: dict[str, Any],
    decided_at: datetime,
    receipts_root: Path,
    max_request_age_days: int,
    max_approval_age_days: int,
    max_defer_age_days: int,
) -> list[str]:
    required = ("decision", "authorizedBy", "reason")
    errors = [f"decision.{field} is required" for field in required if not decision.get(field)]
    receipt_decision = decision.get("decision")
    if receipt_decision not in RECEIPT_DECISIONS:
        errors.append("decision.decision must be APPROVE, REJECT, or DEFER")
    if not _is_human(decision.get("authorizedBy")):
        errors.append("decision.authorizedBy requires explicit human authority")
    if receipt_decision == "APPROVE":
        for field in (
            "decisionMemoryId",
            "visualAcceptanceEvidence",
            "semanticAccessibilityEvidence",
        ):
            if not decision.get(field):
                errors.append(f"decision.{field} is required for APPROVE")
        if request.get("status") != "REVIEWABLE":
            errors.append("APPROVE requires a REVIEWABLE request")
        _validate_request_freshness(
            request,
            decided_at,
            max_request_age_days,
            errors,
        )
        valid_days = int(decision.get("validForDays", max_approval_age_days))
        if valid_days < 1 or valid_days > max_approval_age_days:
            errors.append(
                "decision.validForDays must be between 1 and "
                f"{max_approval_age_days}"
            )
        _validate_accepted_decision(root, decision.get("decisionMemoryId"), errors)
    elif receipt_decision == "DEFER":
        review_after = _parse_datetime(decision.get("reviewAfter"), "decision.reviewAfter", errors)
        if review_after and review_after <= decided_at:
            errors.append("decision.reviewAfter must postdate the decision")
        if review_after and review_after - decided_at > timedelta(days=max_defer_age_days):
            errors.append(
                f"decision.reviewAfter cannot exceed {max_defer_age_days} days"
            )
    active_receipts = _active_receipt_ids(receipts_root, str(request.get("id") or ""))
    supersedes = decision.get("supersedes")
    if active_receipts and not supersedes:
        errors.append(
            "a new decision receipt must supersede the current receipt: "
            + ", ".join(active_receipts)
        )
    elif len(active_receipts) > 1:
        errors.append("existing receipt conflict requires manual resolution")
    elif active_receipts and supersedes != active_receipts[0]:
        errors.append(f"new receipt must supersede active receipt {active_receipts[0]}")
    if supersedes:
        prior = _find_receipt_by_id(receipts_root, str(supersedes))
        if not prior:
            errors.append(f"receipt to supersede was not found: {supersedes}")
        else:
            _, prior_receipt = prior
            if prior_receipt.get("requestId") != request.get("id"):
                errors.append("superseded receipt belongs to a different request")
            prior_decided = _parse_datetime(prior_receipt.get("decidedAt"), "superseded.decidedAt", errors)
            if prior_decided and prior_decided >= decided_at:
                errors.append("superseding receipt must be decided after the prior receipt")
    return errors


def _validate_request_freshness(
    request: dict[str, Any],
    decided_at: datetime,
    max_request_age_days: int,
    errors: list[str],
) -> None:
    requested_at = _parse_datetime(
        request.get("requestedAt"),
        "request.requestedAt",
        errors,
    )
    if not requested_at:
        return
    if requested_at > decided_at:
        errors.append("request.requestedAt cannot postdate the approval decision")
    elif decided_at - requested_at > timedelta(days=max_request_age_days):
        errors.append(
            "request is stale for approval; refresh its evidence after "
            f"{max_request_age_days} days"
        )


def _validate_accepted_decision(root: Path, decision_id: Any, errors: list[str]) -> None:
    decisions = read_jsonl(memory_root(root) / "decisions.jsonl")
    accepted = [
        item
        for item in decisions
        if item.get("id") == decision_id and item.get("status") == "accepted"
    ]
    if not accepted:
        errors.append(f"accepted design-memory decision not found: {decision_id}")


def _bind_human_evidence(
    root: Path,
    path_value: str | Path,
    request_id: str,
    scope: str,
    decided_at: datetime,
) -> dict[str, Any]:
    path = ensure_within(root, path_value)
    evidence = read_json(path, {}) or {}
    errors: list[str] = []
    _validate_human_evidence(evidence, request_id, scope, decided_at, errors)
    if errors:
        raise ValueError("Review receipt denied: " + "; ".join(errors))
    return {
        "path": _relative(root, path),
        "sha256": sha256_file(path),
        "status": evidence["status"],
        "reviewedBy": evidence["reviewedBy"],
        "reviewedAt": evidence["reviewedAt"],
        "scope": evidence["scope"],
    }


def _audit_human_evidence(
    root: Path,
    label: str,
    entry: dict[str, Any],
    request_id: str,
    scope: str,
    decided_at: datetime | None,
    errors: list[str],
) -> None:
    path = _audit_file_binding(root, label, entry, errors)
    if not path:
        return
    evidence = read_json(path, {}) or {}
    _validate_human_evidence(evidence, request_id, scope, decided_at, errors)
    for field in ("status", "reviewedBy", "reviewedAt", "scope"):
        if entry.get(field) != evidence.get(field):
            errors.append(f"{label}.{field} does not match bound evidence")


def _validate_human_evidence(
    evidence: dict[str, Any],
    request_id: str,
    scope: str,
    decided_at: datetime | None,
    errors: list[str],
) -> None:
    if evidence.get("requestId") != request_id:
        errors.append(f"{scope} evidence requestId does not match")
    if evidence.get("status") != "PASS":
        errors.append(f"{scope} evidence status must be PASS")
    if evidence.get("scope") != scope:
        errors.append(f"{scope} evidence scope does not match")
    if not _is_human(evidence.get("reviewedBy")):
        errors.append(f"{scope} evidence requires a human reviewer")
    reviewed_at = _parse_datetime(evidence.get("reviewedAt"), f"{scope}.reviewedAt", errors)
    if reviewed_at and decided_at and reviewed_at > decided_at:
        errors.append(f"{scope} evidence cannot postdate the receipt decision")


def _audit_file_binding(
    root: Path,
    label: str,
    entry: dict[str, Any],
    errors: list[str],
) -> Path | None:
    if not entry.get("path") or not entry.get("sha256"):
        errors.append(f"{label}.path and sha256 are required")
        return None
    try:
        path = ensure_within(root, entry["path"])
    except ValueError as error:
        errors.append(f"{label}: {error}")
        return None
    if not path.is_file():
        errors.append(f"{label}: file missing")
    elif sha256_file(path) != entry["sha256"]:
        errors.append(f"{label}: hash mismatch")
    return path


def _validate_supersession(
    root: Path,
    receipts_root: Path,
    receipt: dict[str, Any],
    decided_at: datetime | None,
    errors: list[str],
) -> None:
    supersedes = receipt.get("supersedes")
    if not supersedes:
        return
    prior = _find_receipt_by_id(receipts_root, str(supersedes))
    if not prior:
        errors.append(f"receipt.supersedes was not found: {supersedes}")
        return
    _, prior_receipt = prior
    if prior_receipt.get("requestId") != receipt.get("requestId"):
        errors.append("receipt.supersedes belongs to a different request")
    prior_decided = _parse_datetime(prior_receipt.get("decidedAt"), "superseded.decidedAt", errors)
    if prior_decided and decided_at and prior_decided >= decided_at:
        errors.append("receipt must postdate the receipt it supersedes")


def _superseding_receipts(
    root: Path,
    receipts_root: Path,
    receipt: dict[str, Any],
) -> list[str]:
    superseding: list[str] = []
    for path in sorted(receipts_root.glob("*.json")):
        candidate = read_json(path, {}) or {}
        if candidate.get("supersedes") != receipt.get("id"):
            continue
        if candidate.get("requestId") != receipt.get("requestId"):
            continue
        audit = audit_baseline_review_receipt(root, path)
        if audit.get("status") == "PASS":
            superseding.append(str(candidate.get("id")))
    return superseding


def _find_receipt_by_id(
    receipts_root: Path,
    receipt_id: str,
) -> tuple[Path, dict[str, Any]] | None:
    for path in sorted(receipts_root.glob("*.json")):
        receipt = read_json(path, {}) or {}
        if receipt.get("id") == receipt_id:
            return path, receipt
    return None


def _active_receipt_ids(receipts_root: Path, request_id: str) -> list[str]:
    receipts = [
        read_json(path, {}) or {}
        for path in sorted(receipts_root.glob("*.json"))
    ]
    superseded = {
        str(receipt.get("supersedes"))
        for receipt in receipts
        if receipt.get("supersedes")
    }
    return [
        str(receipt.get("id"))
        for receipt in receipts
        if receipt.get("requestId") == request_id
        and receipt.get("id")
        and receipt.get("id") not in superseded
    ]


def _receipt_id(receipt: dict[str, Any]) -> str:
    identity = {
        key: value
        for key, value in receipt.items()
        if key != "id"
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16].upper()
    return f"BDR-{digest}"


def _parse_datetime(value: Any, label: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str):
        errors.append(f"{label} must be an ISO-8601 datetime")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{label} must be an ISO-8601 datetime")
        return None
    if parsed.tzinfo is None:
        errors.append(f"{label} must include a timezone")
        return None
    return parsed.astimezone(timezone.utc)


def _is_human(value: Any) -> bool:
    return isinstance(value, str) and value.lower().startswith("human:") and len(value) > 6


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()
