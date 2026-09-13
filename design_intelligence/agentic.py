from __future__ import annotations

import hashlib
import json
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .storage import ensure_within, sha256_file


SCHEMA_VERSION = "1.0.0"
CLAIM_CLASSES = {"ESTABLISHED", "INFERRED", "CONTESTED", "UNKNOWN"}
FAILURE_STATE_KINDS = {"error", "denied", "stale", "offline", "conflict"}
CONFIDENCE_WEIGHTS = {"HIGH": 3, "MODERATE": 2, "LOW": 1, "UNKNOWN": 0}


def build_authority_capsule(
    root: str | Path,
    payload: dict[str, Any],
    *,
    phase: str | None = None,
    max_claims: int | None = None,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """Build a bounded, source-verified context packet for one agent step."""
    document = _mapping(payload, "authority capsule input")
    task_id = _required_text(document, "taskId")
    selected_phase = phase or _required_text(document, "phase")
    limit = max_claims if max_claims is not None else document.get("maxClaims", 20)
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > 100:
        raise ValueError("maxClaims must be an integer from 1 through 100")
    claims = _list(document, "claims", nonempty=True)
    now = as_of or _parse_datetime(document.get("asOf")) or datetime.now(timezone.utc)

    prepared: list[dict[str, Any]] = []
    invalid_sources: list[dict[str, str]] = []
    stale_claims: list[str] = []
    seen: set[str] = set()
    for index, raw_claim in enumerate(claims):
        claim = _mapping(raw_claim, f"claims[{index}]")
        claim_id = _required_text(claim, "id")
        if claim_id in seen:
            raise ValueError(f"duplicate claim id: {claim_id}")
        seen.add(claim_id)
        classification = _required_text(claim, "classification").upper()
        if classification not in CLAIM_CLASSES:
            raise ValueError(f"claims[{index}].classification must be one of {sorted(CLAIM_CLASSES)}")
        authority_rank = claim.get("authorityRank", 100)
        priority = claim.get("priority", 0)
        if not isinstance(authority_rank, int) or isinstance(authority_rank, bool) or authority_rank < 1:
            raise ValueError(f"claims[{index}].authorityRank must be a positive integer")
        if not isinstance(priority, int) or isinstance(priority, bool):
            raise ValueError(f"claims[{index}].priority must be an integer")
        phases = claim.get("phases", [])
        if not isinstance(phases, list) or any(not isinstance(item, str) for item in phases):
            raise ValueError(f"claims[{index}].phases must be a string array")
        if phases and selected_phase not in phases:
            continue

        source_report: dict[str, Any] | None = None
        source = claim.get("source")
        if source is not None:
            source = _mapping(source, f"claims[{index}].source")
            source_path = _required_text(source, "path")
            expected = _required_text(source, "sha256")
            if not _is_sha256(expected):
                raise ValueError(f"claims[{index}].source.sha256 must be a lowercase SHA-256")
            resolved = ensure_within(root, source_path)
            if not resolved.is_file():
                source_report = {"path": source_path, "status": "MISSING", "expectedSha256": expected}
                invalid_sources.append({"claimId": claim_id, "path": source_path, "reason": "MISSING"})
            else:
                actual = sha256_file(resolved)
                status = "VALID" if actual == expected else "DRIFTED"
                source_report = {
                    "path": source_path,
                    "status": status,
                    "expectedSha256": expected,
                    "actualSha256": actual,
                }
                if status != "VALID":
                    invalid_sources.append({"claimId": claim_id, "path": source_path, "reason": status})
        elif classification == "ESTABLISHED":
            invalid_sources.append({"claimId": claim_id, "path": "", "reason": "SOURCE_REQUIRED"})

        expires_at = _parse_datetime(claim.get("expiresAt"))
        stale = bool(expires_at and now > expires_at)
        if stale:
            stale_claims.append(claim_id)
        prepared.append({
            "id": claim_id,
            "statement": _required_text(claim, "statement"),
            "classification": classification,
            "authorityRank": authority_rank,
            "priority": priority,
            "source": source_report,
            "stale": stale,
            "expiresAt": expires_at.isoformat() if expires_at else None,
            "conflictsWith": _string_list(claim.get("conflictsWith", []), f"claims[{index}].conflictsWith"),
            "invalidatedBy": _string_list(claim.get("invalidatedBy", []), f"claims[{index}].invalidatedBy"),
        })

    prepared.sort(key=lambda item: (item["authorityRank"], -item["priority"], item["id"]))
    selected = prepared[:limit]
    omitted = [item["id"] for item in prepared[limit:]]
    selected_ids = {item["id"] for item in selected}
    conflicts = sorted({
        tuple(sorted((item["id"], conflict)))
        for item in selected
        for conflict in item["conflictsWith"]
        if conflict in selected_ids and conflict != item["id"]
    })
    unknowns = [item["id"] for item in selected if item["classification"] == "UNKNOWN"]
    contested = [item["id"] for item in selected if item["classification"] == "CONTESTED"]
    blocking_ids = {item["claimId"] for item in invalid_sources}
    blocking_ids.update(item["id"] for item in selected if item["stale"] and item["classification"] == "ESTABLISHED")
    status = "BLOCKED" if blocking_ids else ("REVIEW_REQUIRED" if conflicts or contested or unknowns else "READY")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "design-intelligence/authority-capsule",
        "status": status,
        "taskId": task_id,
        "phase": selected_phase,
        "asOf": now.isoformat(),
        "claims": selected,
        "omittedClaimIds": omitted,
        "invalidSources": invalid_sources,
        "staleClaimIds": stale_claims,
        "conflicts": [list(item) for item in conflicts],
        "contestedClaimIds": contested,
        "unknownClaimIds": unknowns,
        "revalidationRequired": bool(invalid_sources or stale_claims),
        "implementationAuthorized": False,
        "claimBoundary": "The capsule summarizes bounded evidence; it does not create or transfer repository authority.",
    }


def analyze_ux_state_graph(payload: dict[str, Any]) -> dict[str, Any]:
    """Analyze journey-state reachability, negative states, and recovery coverage."""
    document = _mapping(payload, "UX state graph input")
    journey_id = _required_text(document, "journeyId")
    states = _list(document, "states", nonempty=True)
    transitions = _list(document, "transitions")
    required_kinds = _string_list(document.get("requiredStateKinds", []), "requiredStateKinds")

    state_by_id: dict[str, dict[str, Any]] = {}
    for index, raw_state in enumerate(states):
        state = _mapping(raw_state, f"states[{index}]")
        state_id = _required_text(state, "id")
        if state_id in state_by_id:
            raise ValueError(f"duplicate state id: {state_id}")
        state_by_id[state_id] = {**state, "id": state_id, "kind": _required_text(state, "kind").lower()}

    adjacency: dict[str, list[dict[str, Any]]] = {state_id: [] for state_id in state_by_id}
    normalized_transitions: list[dict[str, Any]] = []
    for index, raw_transition in enumerate(transitions):
        transition = _mapping(raw_transition, f"transitions[{index}]")
        source = _required_text(transition, "from")
        target = _required_text(transition, "to")
        if source not in state_by_id or target not in state_by_id:
            raise ValueError(f"transitions[{index}] references an unknown state")
        normalized = {
            "from": source,
            "to": target,
            "event": _required_text(transition, "event"),
            "recovery": bool(transition.get("recovery", False)),
        }
        adjacency[source].append(normalized)
        normalized_transitions.append(normalized)

    starts = sorted(state_id for state_id, state in state_by_id.items() if state.get("start") is True or state["kind"] == "start")
    successes = sorted(state_id for state_id, state in state_by_id.items() if state.get("success") is True or state["kind"] == "success")
    reachable = _reachable(starts, adjacency)
    unreachable = sorted(set(state_by_id) - reachable)
    dead_ends = sorted(state_id for state_id in reachable if not adjacency[state_id] and state_id not in successes)
    represented_kinds = {state["kind"] for state in state_by_id.values()}
    missing_kinds = sorted(set(kind.lower() for kind in required_kinds) - represented_kinds)
    unrecoverable = sorted(
        state_id
        for state_id, state in state_by_id.items()
        if state["kind"] in FAILURE_STATE_KINDS
        and not any(edge["recovery"] and state_by_id[edge["to"]]["kind"] not in FAILURE_STATE_KINDS for edge in adjacency[state_id])
    )
    success_reachable = bool(set(successes) & reachable)
    gaps: list[dict[str, str]] = []
    if not starts:
        gaps.append({"type": "MISSING_START", "target": journey_id})
    if not successes:
        gaps.append({"type": "MISSING_SUCCESS", "target": journey_id})
    elif not success_reachable:
        gaps.append({"type": "SUCCESS_UNREACHABLE", "target": journey_id})
    gaps.extend({"type": "MISSING_STATE_KIND", "target": kind} for kind in missing_kinds)
    gaps.extend({"type": "UNREACHABLE_STATE", "target": state_id} for state_id in unreachable)
    gaps.extend({"type": "DEAD_END", "target": state_id} for state_id in dead_ends)
    gaps.extend({"type": "MISSING_RECOVERY", "target": state_id} for state_id in unrecoverable)
    scenarios = [
        {
            "id": f"{journey_id.lower()}-{gap['type'].lower().replace('_', '-')}-{gap['target'].lower().replace('_', '-')}",
            "gap": gap,
            "acceptanceCriterion": _scenario_criterion(gap, journey_id),
        }
        for gap in gaps
    ]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "design-intelligence/ux-state-graph",
        "status": "PASS" if not gaps else "REVIEW_REQUIRED",
        "journeyId": journey_id,
        "states": sorted(state_by_id.values(), key=lambda item: item["id"]),
        "transitions": sorted(normalized_transitions, key=lambda item: (item["from"], item["to"], item["event"])),
        "coverage": {
            "startStateIds": starts,
            "successStateIds": successes,
            "successReachable": success_reachable,
            "reachableStateIds": sorted(reachable),
            "unreachableStateIds": unreachable,
            "missingStateKinds": missing_kinds,
            "deadEndStateIds": dead_ends,
            "unrecoverableStateIds": unrecoverable,
        },
        "gaps": gaps,
        "proposedScenarios": scenarios,
        "mutationPerformed": False,
        "claimBoundary": "Proposed scenarios extend the repository's existing test hierarchy only after owner review.",
    }


def simulate_counterfactual(payload: dict[str, Any]) -> dict[str, Any]:
    """Compare proposed directions using declared evidence and falsifiable effects."""
    document = _mapping(payload, "counterfactual input")
    proposal_id = _required_text(document, "proposalId")
    protected = set(_string_list(document.get("protectedBoundaries", []), "protectedBoundaries"))
    alternatives = _list(document, "alternatives", nonempty=True)
    reports: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw_alternative in enumerate(alternatives):
        alternative = _mapping(raw_alternative, f"alternatives[{index}]")
        alternative_id = _required_text(alternative, "id")
        if alternative_id in seen:
            raise ValueError(f"duplicate alternative id: {alternative_id}")
        seen.add(alternative_id)
        effects = _list(alternative, "effects", nonempty=True)
        normalized_effects: list[dict[str, Any]] = []
        uncertainty = 0
        evidence_points = 0
        falsifiable = 0
        for effect_index, raw_effect in enumerate(effects):
            effect = _mapping(raw_effect, f"alternatives[{index}].effects[{effect_index}]")
            confidence = _required_text(effect, "confidence").upper()
            if confidence not in CONFIDENCE_WEIGHTS:
                raise ValueError(f"alternatives[{index}].effects[{effect_index}].confidence is invalid")
            evidence = _string_list(effect.get("evidence", []), f"alternatives[{index}].effects[{effect_index}].evidence")
            falsification = str(effect.get("falsificationTest", "")).strip()
            evidence_points += min(len(evidence), 3)
            falsifiable += int(bool(falsification))
            uncertainty += 3 - CONFIDENCE_WEIGHTS[confidence]
            normalized_effects.append({
                "dimension": _required_text(effect, "dimension"),
                "target": _required_text(effect, "target"),
                "direction": _required_text(effect, "direction"),
                "confidence": confidence,
                "evidence": evidence,
                "falsificationTest": falsification or None,
            })
        rollback_signals = _string_list(alternative.get("rollbackSignals", []), f"alternatives[{index}].rollbackSignals")
        required_evidence = _string_list(alternative.get("requiredEvidence", []), f"alternatives[{index}].requiredEvidence")
        boundary_impacts = _list(alternative, "boundaryImpacts")
        unapproved_boundaries: list[str] = []
        for boundary_index, raw_impact in enumerate(boundary_impacts):
            impact = _mapping(raw_impact, f"alternatives[{index}].boundaryImpacts[{boundary_index}]")
            boundary = _required_text(impact, "boundary")
            if boundary in protected and impact.get("status") != "APPROVED":
                unapproved_boundaries.append(boundary)
        missing_falsification = len(normalized_effects) - falsifiable
        decision_score = (
            evidence_points * 2
            + falsifiable * 2
            + min(len(required_evidence), 5)
            + min(len(rollback_signals), 3) * 2
            - uncertainty * 2
            - missing_falsification * 3
            - len(unapproved_boundaries) * 100
        )
        reports.append({
            "id": alternative_id,
            "summary": _required_text(alternative, "summary"),
            "effects": normalized_effects,
            "requiredEvidence": required_evidence,
            "rollbackSignals": rollback_signals,
            "unapprovedProtectedBoundaries": sorted(set(unapproved_boundaries)),
            "missingFalsificationCount": missing_falsification,
            "uncertaintyPoints": uncertainty,
            "decisionScore": decision_score,
            "eligibleForSelection": not unapproved_boundaries and missing_falsification == 0 and bool(rollback_signals),
        })
    ranked = sorted(reports, key=lambda item: (-item["decisionScore"], item["id"]))
    eligible = [item for item in ranked if item["eligibleForSelection"]]
    recommendation = eligible[0]["id"] if eligible and (len(eligible) == 1 or eligible[0]["decisionScore"] > eligible[1]["decisionScore"]) else None
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "design-intelligence/counterfactual-report",
        "status": "BLOCKED" if not eligible else "READY_FOR_HUMAN_SELECTION",
        "proposalId": proposal_id,
        "alternatives": ranked,
        "recommendedAlternativeId": recommendation,
        "humanSelectionRequired": True,
        "implementationAuthorized": False,
        "claimBoundary": "Scores compare declared evidence and risks; they do not approve a direction or predict production outcomes.",
    }


def evaluate_design_arena(payload: dict[str, Any]) -> dict[str, Any]:
    """Blind-score comparable, isolated design variants without executing them."""
    document = _mapping(payload, "design arena input")
    arena_id = _required_text(document, "arenaId")
    contract_hash = _required_text(document, "contractHash")
    if not _is_sha256(contract_hash):
        raise ValueError("contractHash must be a lowercase SHA-256")
    validation_plan_hash = _required_text(document, "validationPlanHash")
    if not _is_sha256(validation_plan_hash):
        raise ValueError("validationPlanHash must be a lowercase SHA-256")
    required_dimensions = _string_list(document.get("requiredEvidenceDimensions", []), "requiredEvidenceDimensions")
    minimum_reviews = _integer(document.get("minimumIndependentReviews", 2), "minimumIndependentReviews", minimum=1)
    variants = _list(document, "variants", nonempty=True)
    if len(variants) < 2:
        raise ValueError("design arena requires at least two variants")
    reports: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw_variant in enumerate(variants):
        variant = _mapping(raw_variant, f"variants[{index}]")
        variant_id = _required_text(variant, "id")
        if variant_id in seen:
            raise ValueError(f"duplicate variant id: {variant_id}")
        seen.add(variant_id)
        evidence = _mapping(variant.get("evidence"), f"variants[{index}].evidence")
        dimensions = _string_list(evidence.get("dimensions", []), f"variants[{index}].evidence.dimensions")
        missing_dimensions = sorted(set(required_dimensions) - set(dimensions))
        quality_score = _number(evidence.get("qualityScore"), f"variants[{index}].evidence.qualityScore", minimum=0, maximum=100)
        critical = _integer(evidence.get("criticalAccessibilityViolations", 0), f"variants[{index}].evidence.criticalAccessibilityViolations", minimum=0)
        serious = _integer(evidence.get("seriousAccessibilityViolations", 0), f"variants[{index}].evidence.seriousAccessibilityViolations", minimum=0)
        tests_passed = _integer(evidence.get("testsPassed", 0), f"variants[{index}].evidence.testsPassed", minimum=0)
        tests_total = _integer(evidence.get("testsTotal", 0), f"variants[{index}].evidence.testsTotal", minimum=0)
        raw_reviews = _list(variant, "reviews", nonempty=True)
        reviews: list[dict[str, Any]] = []
        reviewer_ids: set[str] = set()
        for review_index, raw_review in enumerate(raw_reviews):
            review = _mapping(raw_review, f"variants[{index}].reviews[{review_index}]")
            reviewer_id = _required_text(review, "reviewerId")
            if reviewer_id in reviewer_ids:
                raise ValueError(f"variants[{index}] contains duplicate reviewer id: {reviewer_id}")
            reviewer_ids.add(reviewer_id)
            verdict = _required_text(review, "verdict").upper()
            if verdict not in {"PASS", "REVIEW_REQUIRED", "BLOCKED"}:
                raise ValueError(f"variants[{index}].reviews[{review_index}].verdict is invalid")
            reviews.append({
                "reviewerId": reviewer_id,
                "verdict": verdict,
                "findings": _string_list(review.get("findings", []), f"variants[{index}].reviews[{review_index}].findings"),
            })
        review_coverage = len(reviewer_ids) >= minimum_reviews
        review_blocked = any(review["verdict"] == "BLOCKED" for review in reviews)
        dissent = len({review["verdict"] for review in reviews}) > 1
        contract_matches = variant.get("contractHash") == contract_hash
        validation_plan_matches = variant.get("validationPlanHash") == validation_plan_hash
        isolated = variant.get("workspaceIsolation") is True
        receipt_passes = variant.get("buildReceiptStatus") == "PASS"
        proof_complete = evidence.get("proofComplete") is True
        tests_complete = tests_total > 0 and tests_passed == tests_total
        eligible = all((contract_matches, validation_plan_matches, isolated, receipt_passes, proof_complete, tests_complete, critical == 0, serious == 0, not missing_dimensions, review_coverage, not review_blocked))
        score = round(quality_score + (tests_passed / tests_total * 10 if tests_total else 0), 3)
        blind_label = "variant-" + hashlib.sha256(f"{contract_hash}:{variant_id}".encode("utf-8")).hexdigest()[:8]
        reports.append({
            "variantId": variant_id,
            "blindLabel": blind_label,
            "eligible": eligible,
            "score": score,
            "qualityScore": quality_score,
            "tests": {"passed": tests_passed, "total": tests_total},
            "missingEvidenceDimensions": missing_dimensions,
            "reviews": reviews,
            "dissent": dissent,
            "gates": {
                "contractMatches": contract_matches,
                "validationPlanMatches": validation_plan_matches,
                "workspaceIsolated": isolated,
                "buildReceiptPasses": receipt_passes,
                "proofComplete": proof_complete,
                "testsComplete": tests_complete,
                "accessibilityPasses": critical == 0 and serious == 0,
                "independentReviewCoverage": review_coverage,
                "reviewBlockAbsent": not review_blocked,
            },
        })
    ranked = sorted(reports, key=lambda item: (-item["score"], item["blindLabel"]))
    eligible = [item for item in ranked if item["eligible"]]
    leader = eligible[0]["variantId"] if eligible and (len(eligible) == 1 or eligible[0]["score"] > eligible[1]["score"]) else None
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "design-intelligence/design-arena-report",
        "status": "BLOCKED" if not eligible else "READY_FOR_HUMAN_SELECTION",
        "arenaId": arena_id,
        "contractHash": contract_hash,
        "validationPlanHash": validation_plan_hash,
        "minimumIndependentReviews": minimum_reviews,
        "variants": ranked,
        "leaderVariantId": leader,
        "humanSelectionRequired": True,
        "executionPerformed": False,
        "implementationAuthorized": False,
        "claimBoundary": "The arena compares supplied, contract-equivalent evidence and independent critiques; AgentFlow remains the execution authority and a human selects the direction.",
    }


def assess_outcome(payload: dict[str, Any], *, as_of: datetime | None = None) -> dict[str, Any]:
    """Evaluate a bounded product outcome and agent-effectiveness contract."""
    document = _mapping(payload, "outcome assessment input")
    contract = _mapping(document.get("contract"), "contract")
    contract_id = _required_text(contract, "id")
    journey_id = _required_text(contract, "journeyId")
    decision_id = str(contract.get("decisionId", "")).strip() or None
    window = _mapping(contract.get("observationWindow"), "contract.observationWindow")
    start = _parse_datetime(_required_text(window, "start"))
    end = _parse_datetime(_required_text(window, "end"))
    assert start is not None and end is not None
    if end <= start:
        raise ValueError("contract.observationWindow.end must be after start")
    now = as_of or _parse_datetime(document.get("asOf")) or datetime.now(timezone.utc)
    release_evidence = _string_list(document.get("releaseEvidence", []), "releaseEvidence")
    success = _evaluate_signals(_list(contract, "successSignals", nonempty=True), "contract.successSignals")
    counters = _evaluate_signals(_list(contract, "counterSignals"), "contract.counterSignals")
    agent = _evaluate_signals(_list(document, "agentSignals"), "agentSignals")
    missing_signals = [item["id"] for item in success + counters if not item["evidencePresent"]]
    observation_complete = now >= end
    assessable = observation_complete and bool(release_evidence) and not missing_signals
    counter_triggered = any(not item["passes"] for item in counters)
    if not assessable:
        outcome_status = "NOT_READY"
    elif counter_triggered:
        outcome_status = "COUNTER_SIGNAL"
    elif all(item["passes"] for item in success):
        outcome_status = "SUCCESS"
    else:
        outcome_status = "INCONCLUSIVE"
    candidate_eligible = outcome_status == "SUCCESS" and decision_id is not None
    memory_candidate = {
        "eligible": candidate_eligible,
        "ratificationStatus": "HUMAN_REQUIRED",
        "contractId": contract_id,
        "journeyId": journey_id,
        "decisionId": decision_id,
        "outcomeStatus": outcome_status,
        "reason": str(contract.get("reason", "")).strip() or f"Outcome contract {contract_id} met its declared success and counter-signal thresholds.",
        "lesson": str(contract.get("lesson", "")).strip() or "Retain only after human review of the bound outcome evidence.",
        "product": contract.get("product"),
        "surface": contract.get("surface"),
        "component": contract.get("component"),
        "sourceEvidence": sorted(set(release_evidence + [source for item in success + counters for source in item["evidence"]])),
    }
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "design-intelligence/outcome-assessment",
        "status": "PASS" if assessable else "BLOCKED",
        "contractId": contract_id,
        "journeyId": journey_id,
        "asOf": now.isoformat(),
        "observationWindow": {"start": start.isoformat(), "end": end.isoformat(), "complete": observation_complete},
        "releaseEvidencePresent": bool(release_evidence),
        "missingSignalIds": missing_signals,
        "outcomeStatus": outcome_status,
        "successSignals": success,
        "counterSignals": counters,
        "agentEffectiveness": {
            "status": "NOT_MEASURED" if not agent else ("PASS" if all(item["passes"] and item["evidencePresent"] for item in agent) else "REVIEW_REQUIRED"),
            "signals": agent,
        },
        "memoryCandidate": memory_candidate,
        "memoryMutationPerformed": False,
        "claimBoundary": "A completed assessment is not deployment, production success, customer acceptance, or authority to promote institutional memory.",
    }


def _evaluate_signals(raw_signals: list[Any], label: str) -> list[dict[str, Any]]:
    operators: dict[str, Callable[[float, float], bool]] = {
        ">=": lambda actual, threshold: actual >= threshold,
        ">": lambda actual, threshold: actual > threshold,
        "<=": lambda actual, threshold: actual <= threshold,
        "<": lambda actual, threshold: actual < threshold,
        "==": lambda actual, threshold: actual == threshold,
    }
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw_signal in enumerate(raw_signals):
        signal = _mapping(raw_signal, f"{label}[{index}]")
        signal_id = _required_text(signal, "id")
        if signal_id in seen:
            raise ValueError(f"duplicate signal id in {label}: {signal_id}")
        seen.add(signal_id)
        operator = _required_text(signal, "operator")
        if operator not in operators:
            raise ValueError(f"{label}[{index}].operator must be one of {sorted(operators)}")
        actual = _number(signal.get("actual"), f"{label}[{index}].actual")
        threshold = _number(signal.get("threshold"), f"{label}[{index}].threshold")
        evidence = _string_list(signal.get("evidence", []), f"{label}[{index}].evidence")
        results.append({
            "id": signal_id,
            "actual": actual,
            "operator": operator,
            "threshold": threshold,
            "passes": operators[operator](actual, threshold),
            "evidencePresent": bool(evidence),
            "evidence": evidence,
        })
    return results


def _reachable(starts: list[str], adjacency: dict[str, list[dict[str, Any]]]) -> set[str]:
    visited: set[str] = set()
    queue = deque(starts)
    while queue:
        state = queue.popleft()
        if state in visited:
            continue
        visited.add(state)
        queue.extend(edge["to"] for edge in adjacency.get(state, []))
    return visited


def _scenario_criterion(gap: dict[str, str], journey_id: str) -> str:
    gap_type = gap["type"]
    target = gap["target"]
    if gap_type == "MISSING_STATE_KIND":
        return f"The existing {journey_id} scenario exercises and verifies the {target} state."
    if gap_type == "MISSING_RECOVERY":
        return f"A user can recover from state {target} through an explicit, verified transition."
    if gap_type == "UNREACHABLE_STATE":
        return f"State {target} is reachable from a declared journey start or is removed with owner approval."
    if gap_type == "DEAD_END":
        return f"State {target} provides a verified next action or is declared a terminal success state."
    return f"Journey {journey_id} has a reachable start-to-success path verified by its existing test hierarchy."


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _list(document: dict[str, Any], field: str, nonempty: bool = False) -> list[Any]:
    value = document.get(field, [])
    if not isinstance(value, list) or (nonempty and not value):
        qualifier = "a non-empty array" if nonempty else "an array"
        raise ValueError(f"{field} must be {qualifier}")
    return value


def _required_text(document: dict[str, Any], field: str) -> str:
    value = document.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")
    return value.strip()


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{label} must be a string array")
    return [item.strip() for item in value]


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid ISO-8601 datetime: {value}") from exc
    if parsed.tzinfo is None:
        raise ValueError("datetime must include a timezone")
    return parsed


def _number(value: Any, label: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} must be a number")
    number = float(value)
    if minimum is not None and number < minimum:
        raise ValueError(f"{label} must be at least {minimum}")
    if maximum is not None and number > maximum:
        raise ValueError(f"{label} must be at most {maximum}")
    return number


def _integer(value: Any, label: str, *, minimum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{label} must be at least {minimum}")
    return value


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
