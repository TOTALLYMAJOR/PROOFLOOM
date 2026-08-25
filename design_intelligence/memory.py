from __future__ import annotations

import json
from datetime import date, datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any

from .models import AuthorityLevel, DecisionStatus, MemoryContext, OutcomeResult
from .repository import inspect_repository
from .storage import append_jsonl, atomic_write_json, ensure_within, read_json, read_jsonl, sha256_file


MEMORY_FILES = {
    "decisions": "decisions.jsonl",
    "outcomes": "outcomes.jsonl",
    "exceptions": "exceptions.jsonl",
    "debt": "debt.jsonl",
    "registry": "component-registry.json",
    "rules": "product-rules.json",
}

PROTECTED_CATEGORIES = {"accessibility", "safety", "semantic-correctness", "product-requirement"}
DECISION_CLASSES = {
    DecisionStatus.ACCEPTED.value: "binding",
    DecisionStatus.PROPOSED.value: "advisory",
    DecisionStatus.EXPERIMENTAL.value: "advisory",
    DecisionStatus.SUPERSEDED.value: "historical",
    DecisionStatus.DEPRECATED.value: "historical",
    DecisionStatus.REJECTED.value: "historical",
}
AUTHORITY_ORDER = {
    AuthorityLevel.PORTFOLIO.value: 0,
    AuthorityLevel.ARCHETYPE.value: 1,
    AuthorityLevel.PRODUCT.value: 2,
    AuthorityLevel.SURFACE.value: 3,
    AuthorityLevel.COMPONENT.value: 4,
    AuthorityLevel.EXCEPTION.value: 5,
}


def memory_root(repository_root: str | Path) -> Path:
    return Path(repository_root).resolve() / ".design" / "memory"


def initialize_memory(
    repository_root: str | Path,
    allow_existing_authority: bool = False,
    memory_only: bool = False,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    destination = memory_root(root)
    snapshot = inspect_repository(root)
    competing = [
        path
        for path in snapshot.institutional_design_memory.authority_paths
        if not path.startswith(".design/memory")
        and not path.startswith("tests/fixtures/")
    ]
    if competing and not destination.exists() and not allow_existing_authority:
        raise ValueError(
            "Existing design-decision authority detected; integrate with it instead of creating .design/memory: "
            + ", ".join(competing)
        )
    destination.mkdir(parents=True, exist_ok=True)
    for filename in ("decisions.jsonl", "outcomes.jsonl", "exceptions.jsonl", "debt.jsonl"):
        path = destination / filename
        if not path.exists():
            path.touch()
    defaults = files("design_intelligence").joinpath("data/defaults/product-rules.json")
    rules_path = destination / MEMORY_FILES["rules"]
    if not rules_path.exists():
        atomic_write_json(rules_path, json.loads(defaults.read_text(encoding="utf-8")))
    registry_path = destination / MEMORY_FILES["registry"]
    if not registry_path.exists():
        atomic_write_json(
            registry_path,
            {"schemaVersion": 1, "generatedAt": None, "components": [], "source": "uninitialized"},
        )
    schema_root = destination / "schemas"
    schema_root.mkdir(parents=True, exist_ok=True)
    schema_source = files("design_intelligence").joinpath("data/schemas")
    for schema_name in (
        "design-contract.schema.json",
        "design-decision.schema.json",
        "design-exception.schema.json",
        "design-outcome.schema.json",
        "design-memory-preflight.schema.json",
        "baseline-review-request.schema.json",
        "baseline-review-receipt.schema.json",
        "repair-plan.schema.json",
        "validation-evidence.schema.json",
        "reference-analysis.schema.json",
        "design-adoption-report.schema.json",
    ):
        schema_path = schema_root / schema_name
        if not schema_path.exists():
            atomic_write_json(schema_path, json.loads(schema_source.joinpath(schema_name).read_text(encoding="utf-8")))
    if not memory_only:
        quality_root = root / ".design/quality"
        quality_root.mkdir(parents=True, exist_ok=True)
        thresholds_path = quality_root / "thresholds.json"
        if not thresholds_path.exists():
            thresholds = files("design_intelligence").joinpath("data/defaults/quality-thresholds.json")
            atomic_write_json(thresholds_path, json.loads(thresholds.read_text(encoding="utf-8")))
        history_path = quality_root / "history.jsonl"
        if not history_path.exists():
            history_path.touch()
        baseline_manifest = root / ".design/baselines/manifest.json"
        if not baseline_manifest.exists():
            atomic_write_json(baseline_manifest, {"schemaVersion": 1, "scenarios": {}})
        review_policy_path = root / ".design/baselines/review-policy.json"
        if not review_policy_path.exists():
            review_policy = files("design_intelligence").joinpath(
                "data/defaults/baseline-review-policy.json"
            )
            atomic_write_json(
                review_policy_path,
                json.loads(review_policy.read_text(encoding="utf-8")),
            )
    return {
        "status": "READY",
        "root": str(destination),
        "files": sorted(str(path.relative_to(root)) for path in destination.iterdir()),
        "integratedExistingAuthority": bool(competing),
        "memoryOnly": memory_only,
    }


def append_decision(repository_root: str | Path, decision: dict[str, Any]) -> dict[str, Any]:
    root = memory_root(repository_root)
    existing = read_jsonl(root / MEMORY_FILES["decisions"])
    outcomes = read_jsonl(root / MEMORY_FILES["outcomes"])
    errors = validate_decision(decision, existing, outcomes)
    if errors:
        raise ValueError("Invalid design decision: " + "; ".join(errors))
    record = dict(decision)
    record.setdefault("revision", _next_revision(existing, record["id"]))
    append_jsonl(root / MEMORY_FILES["decisions"], record)
    return record


def append_outcome(repository_root: str | Path, outcome: dict[str, Any]) -> dict[str, Any]:
    root = memory_root(repository_root)
    errors = validate_outcome(outcome, read_jsonl(root / MEMORY_FILES["decisions"]))
    if errors:
        raise ValueError("Invalid design outcome: " + "; ".join(errors))
    if any(item.get("id") == outcome.get("id") for item in read_jsonl(root / MEMORY_FILES["outcomes"])):
        raise ValueError(f"Duplicate outcome id: {outcome.get('id')}")
    append_jsonl(root / MEMORY_FILES["outcomes"], outcome)
    return outcome


def append_exception(repository_root: str | Path, exception: dict[str, Any]) -> dict[str, Any]:
    root = memory_root(repository_root)
    errors = validate_exception(exception)
    if errors:
        raise ValueError("Invalid design exception: " + "; ".join(errors))
    if any(item.get("id") == exception.get("id") for item in read_jsonl(root / MEMORY_FILES["exceptions"])):
        raise ValueError(f"Duplicate exception id: {exception.get('id')}")
    append_jsonl(root / MEMORY_FILES["exceptions"], exception)
    return exception


def append_debt(repository_root: str | Path, debt: dict[str, Any]) -> dict[str, Any]:
    required = ("id", "status", "description", "scope", "owner", "createdAt", "reviewAfter")
    errors = [f"Missing required field: {field}" for field in required if not debt.get(field)]
    if debt.get("status") not in {"open", "resolved", "accepted"}:
        errors.append("status must be open, resolved, or accepted")
    if errors:
        raise ValueError("Invalid design debt: " + "; ".join(errors))
    root = memory_root(repository_root)
    append_jsonl(root / MEMORY_FILES["debt"], debt)
    return debt


def validate_decision(
    decision: dict[str, Any],
    existing: list[dict[str, Any]] | None = None,
    outcomes: list[dict[str, Any]] | None = None,
    enforce_lifecycle: bool = True,
) -> list[str]:
    required = (
        "id", "status", "authorityLevel", "decision", "problem", "evidence", "alternatives",
        "reason", "affectedComponents", "createdAt",
    )
    errors = [f"Missing required field: {field}" for field in required if field not in decision]
    if not str(decision.get("id", "")).startswith("DL-"):
        errors.append("id must start with DL-")
    try:
        status = DecisionStatus(decision.get("status"))
    except ValueError:
        errors.append("Unknown decision status")
        status = None
    try:
        level = AuthorityLevel(decision.get("authorityLevel"))
    except ValueError:
        errors.append("Unknown authority level")
        level = None
    if level == AuthorityLevel.PRODUCT and not decision.get("product"):
        errors.append("Product-level decisions require product")
    if level == AuthorityLevel.SURFACE and not decision.get("surface"):
        errors.append("Surface-level decisions require surface")
    if level == AuthorityLevel.COMPONENT and not decision.get("component"):
        errors.append("Component-level decisions require component")
    _validate_iso_datetime(decision.get("createdAt"), "createdAt", errors)
    if status == DecisionStatus.ACCEPTED:
        promotion = decision.get("promotion") or {}
        authorized_by = promotion.get("authorizedBy", "")
        if not promotion.get("validationEvidence"):
            errors.append("Accepted decisions require promotion.validationEvidence")
        if not promotion.get("outcomeId"):
            errors.append("Accepted decisions require promotion.outcomeId")
        elif outcomes is not None:
            promotion_outcome = next(
                (item for item in outcomes if item.get("id") == promotion["outcomeId"]),
                None,
            )
            if promotion_outcome is None:
                errors.append(f"Promotion outcome not found: {promotion['outcomeId']}")
            else:
                if promotion_outcome.get("decisionId") != decision.get("id"):
                    errors.append("Promotion outcome must belong to the promoted decision")
                if promotion_outcome.get("result") != OutcomeResult.ACCEPTED.value:
                    errors.append("Promotion outcome must be accepted")
        if level in {AuthorityLevel.PORTFOLIO, AuthorityLevel.ARCHETYPE, AuthorityLevel.PRODUCT}:
            if authorized_by == "quality-gate" or authorized_by.startswith("agent") or not authorized_by:
                errors.append("Portfolio, archetype, and product law promotion requires explicit human authority")
        elif not authorized_by:
            errors.append("Accepted local decisions require promotion.authorizedBy")
    supersedes = decision.get("supersedes")
    proposes_supersession = decision.get("proposesSupersession")
    if enforce_lifecycle:
        if supersedes == decision.get("id") or proposes_supersession == decision.get("id"):
            errors.append("A decision cannot supersede itself")
        if status in {DecisionStatus.PROPOSED, DecisionStatus.EXPERIMENTAL, DecisionStatus.REJECTED} and supersedes:
            errors.append("Proposed, experimental, and rejected decisions cannot declare supersedes")
        if status not in {DecisionStatus.PROPOSED, DecisionStatus.EXPERIMENTAL} and proposes_supersession:
            errors.append("Only proposed or experimental decisions may declare proposesSupersession")
        if status == DecisionStatus.SUPERSEDED and not decision.get("supersededBy"):
            errors.append("Superseded decisions require supersededBy")
        if status != DecisionStatus.SUPERSEDED and decision.get("supersededBy"):
            errors.append("Only superseded decisions may declare supersededBy")
    if decision.get("category") in PROTECTED_CATEGORIES and decision.get("overrides"):
        errors.append("Protected categories cannot override broader rules")
    if existing is not None:
        prior = [item for item in existing if item.get("id") == decision.get("id")]
        if prior:
            expected = max(int(item.get("revision", 1)) for item in prior) + 1
            if int(decision.get("revision", expected)) != expected:
                errors.append(f"Revision for {decision.get('id')} must be {expected}")
        latest = {item.get("id"): item for item in _latest_decision_revisions(existing)}
        if enforce_lifecycle:
            target_id = supersedes or proposes_supersession
            if target_id and target_id not in latest:
                errors.append(f"Supersession target not found: {target_id}")
            if status == DecisionStatus.SUPERSEDED:
                successor = latest.get(decision.get("supersededBy"))
                if successor is None:
                    errors.append(f"Superseding decision not found: {decision.get('supersededBy')}")
                elif successor.get("status") != DecisionStatus.ACCEPTED.value:
                    errors.append("Superseding decision must be accepted")
                elif successor.get("supersedes") != decision.get("id"):
                    errors.append("supersededBy must reference a decision that supersedes this decision")
    return errors


def validate_outcome(outcome: dict[str, Any], decisions: list[dict[str, Any]] | None = None) -> list[str]:
    required = ("id", "decisionId", "result", "reason", "evidence", "lesson", "recordedAt")
    errors = [f"Missing required field: {field}" for field in required if not outcome.get(field)]
    if not str(outcome.get("id", "")).startswith("DO-"):
        errors.append("id must start with DO-")
    try:
        OutcomeResult(outcome.get("result"))
    except ValueError:
        errors.append("Unknown outcome result")
    _validate_iso_datetime(outcome.get("recordedAt"), "recordedAt", errors)
    if decisions is not None and not any(item.get("id") == outcome.get("decisionId") for item in decisions):
        errors.append(f"Decision not found: {outcome.get('decisionId')}")
    return errors


def validate_exception(exception: dict[str, Any]) -> list[str]:
    required = ("id", "reason", "scope", "owner", "createdAt", "expiresAt", "status")
    errors = [f"Missing required field: {field}" for field in required if not exception.get(field)]
    if not str(exception.get("id", "")).startswith("DX-"):
        errors.append("id must start with DX-")
    if exception.get("status") not in {"active", "expired", "revoked"}:
        errors.append("Unknown exception status")
    _validate_iso_datetime(exception.get("createdAt"), "createdAt", errors)
    _validate_iso_date(exception.get("expiresAt"), "expiresAt", errors)
    if set(exception.get("categories", [])) & PROTECTED_CATEGORIES:
        errors.append("Exceptions cannot weaken accessibility, safety, semantic correctness, or product requirements")
    return errors


def retrieve_context(
    repository_root: str | Path,
    product: str | None = None,
    archetype: str | None = None,
    surface: str | None = None,
    component: str | None = None,
    max_records: int = 40,
    as_of: date | None = None,
    include_descendants: bool = False,
) -> MemoryContext:
    root = memory_root(repository_root)
    max_records = max(1, min(max_records, 100))
    today = as_of or date.today()
    rules = read_json(root / MEMORY_FILES["rules"], {}) or {}
    resolved_archetype = archetype or _product_archetype(rules, product)
    inherited, conflicts = _resolve_rules(rules, product, resolved_archetype)
    decisions = _latest_decision_revisions(read_jsonl(root / MEMORY_FILES["decisions"]))
    relevant_decisions = [
        {**item, "memoryClass": DECISION_CLASSES.get(item.get("status"), "unknown")}
        for item in decisions
        if _matches_scope(
            item,
            product,
            resolved_archetype,
            surface,
            component,
            include_descendants=include_descendants,
        )
    ]
    relevant_decisions.sort(key=lambda item: (AUTHORITY_ORDER.get(item.get("authorityLevel", "portfolio"), 0), item.get("createdAt", "")))
    exceptions = [
        item
        for item in read_jsonl(root / MEMORY_FILES["exceptions"])
        if _matches_scope(
            item.get("scope", {}),
            product,
            resolved_archetype,
            surface,
            component,
            include_descendants=include_descendants,
        )
        and item.get("status") == "active"
        and _date_on_or_after(item.get("expiresAt"), today)
    ]
    protected_ids = {item["id"] for item in inherited if item.get("protected")}
    active_exceptions: list[dict[str, Any]] = []
    for item in exceptions:
        invalid_rules = protected_ids.intersection(item.get("ruleIds", []))
        if invalid_rules:
            conflicts.append({"exceptionId": item.get("id"), "protectedRuleIds": sorted(invalid_rules)})
        else:
            active_exceptions.append(item)
    outcomes = [
        item
        for item in read_jsonl(root / MEMORY_FILES["outcomes"])
        if item.get("result") == "rejected"
        and _matches_scope(
            item,
            product,
            resolved_archetype,
            surface,
            component,
            include_descendants=include_descendants,
        )
    ]
    debt = [
        item
        for item in read_jsonl(root / MEMORY_FILES["debt"])
        if item.get("status") == "open"
        and _matches_scope(
            item.get("scope", {}),
            product,
            resolved_archetype,
            surface,
            component,
            include_descendants=include_descendants,
        )
    ]
    stale = find_stale_records(repository_root, as_of=today)
    total = len(relevant_decisions) + len(active_exceptions) + len(outcomes) + len(debt) + len(stale)
    budget = max_records
    selected_decisions, budget = _take(relevant_decisions, budget)
    selected_exceptions, budget = _take(active_exceptions, budget)
    selected_outcomes, budget = _take(outcomes, budget)
    selected_debt, budget = _take(debt, budget)
    selected_stale, _ = _take(stale, budget)
    binding_decisions = [item for item in selected_decisions if item["memoryClass"] == "binding"]
    advisory_decisions = [item for item in selected_decisions if item["memoryClass"] == "advisory"]
    historical_decisions = [item for item in selected_decisions if item["memoryClass"] == "historical"]
    return MemoryContext(
        product=product,
        archetype=resolved_archetype,
        surface=surface,
        component=component,
        inherited_rules=inherited,
        decisions=selected_decisions,
        binding_decisions=binding_decisions,
        advisory_decisions=advisory_decisions,
        historical_decisions=historical_decisions,
        active_exceptions=selected_exceptions,
        rejected_outcomes=selected_outcomes,
        unresolved_debt=selected_debt,
        stale_records=selected_stale,
        conflicts=conflicts,
        bounded=total > max_records,
        total_available=total,
    )


def find_stale_records(repository_root: str | Path, as_of: date | None = None) -> list[dict[str, Any]]:
    root = memory_root(repository_root)
    today = as_of or date.today()
    stale: list[dict[str, Any]] = []
    for item in _latest_decision_revisions(read_jsonl(root / MEMORY_FILES["decisions"])):
        review_after = item.get("reviewAfter")
        if item.get("status") == "accepted" and review_after and _date_before(review_after, today):
            stale.append({"type": "decision", "id": item.get("id"), "reason": f"reviewAfter {review_after} passed"})
    for item in read_jsonl(root / MEMORY_FILES["exceptions"]):
        expires = item.get("expiresAt")
        if item.get("status") == "active" and expires and _date_before(expires, today):
            stale.append({"type": "exception", "id": item.get("id"), "reason": f"expiresAt {expires} passed"})
    for item in read_jsonl(root / MEMORY_FILES["debt"]):
        review_after = item.get("reviewAfter")
        if item.get("status") == "open" and review_after and _date_before(review_after, today):
            stale.append({"type": "debt", "id": item.get("id"), "reason": f"reviewAfter {review_after} passed"})
    return sorted(stale, key=lambda item: (item["type"], str(item["id"])))


def audit_memory(repository_root: str | Path, as_of: date | None = None) -> dict[str, Any]:
    repository = Path(repository_root).resolve()
    root = memory_root(repository)
    errors: list[str] = []
    warnings: list[str] = []
    required_files = (
        MEMORY_FILES["decisions"],
        MEMORY_FILES["outcomes"],
        MEMORY_FILES["exceptions"],
        MEMORY_FILES["debt"],
    )
    errors.extend(
        f"Required design-memory file is missing: .design/memory/{filename}"
        for filename in required_files
        if not (root / filename).is_file()
    )
    rules = read_json(root / MEMORY_FILES["rules"], {}) or {}
    errors.extend(_audit_source_authorities(repository, rules))
    decisions = read_jsonl(root / MEMORY_FILES["decisions"])
    outcomes = read_jsonl(root / MEMORY_FILES["outcomes"])
    exceptions = read_jsonl(root / MEMORY_FILES["exceptions"])
    seen_outcomes: set[str] = set()
    for item in outcomes:
        errors.extend(f"{item.get('id', '<unknown>')}: {error}" for error in validate_outcome(item, decisions))
        if item.get("id") in seen_outcomes:
            errors.append(f"Duplicate outcome id: {item.get('id')}")
        seen_outcomes.add(item.get("id"))
    for item in decisions:
        errors.extend(
            f"{item.get('id', '<unknown>')}: {error}"
            for error in validate_decision(item, None, outcomes, enforce_lifecycle=False)
        )
    errors.extend(_audit_decision_lifecycle(decisions, outcomes))
    for item in exceptions:
        errors.extend(f"{item.get('id', '<unknown>')}: {error}" for error in validate_exception(item))
    stale = find_stale_records(repository_root, as_of)
    if stale:
        warnings.append(f"{len(stale)} stale or expired record(s) require review")
    context = retrieve_context(
        repository_root,
        max_records=100,
        as_of=as_of,
        include_descendants=True,
    )
    if context.conflicts:
        errors.append(f"{len(context.conflicts)} protected-rule conflict(s) detected")
    return {
        "status": "PASS" if not errors else "FAIL",
        "counts": {
            "decisions": len(decisions),
            "outcomes": len(outcomes),
            "exceptions": len(exceptions),
            "debt": len(read_jsonl(root / MEMORY_FILES["debt"])),
            "stale": len(stale),
        },
        "errors": errors,
        "warnings": warnings,
        "stale": stale,
    }


def preflight_memory(
    repository_root: str | Path,
    product: str | None = None,
    archetype: str | None = None,
    surface: str | None = None,
    component: str | None = None,
    max_records: int = 40,
    as_of: date | None = None,
) -> dict[str, Any]:
    audit = audit_memory(repository_root, as_of=as_of)
    context = retrieve_context(
        repository_root,
        product=product,
        archetype=archetype,
        surface=surface,
        component=component,
        max_records=max_records,
        as_of=as_of,
        include_descendants=True,
    )
    blockers = list(audit["errors"])
    blockers.extend(
        f"Scoped rule conflict: {json.dumps(conflict, sort_keys=True)}"
        for conflict in context.conflicts
    )
    blockers = list(dict.fromkeys(blockers))
    warnings = list(audit["warnings"])
    warning_groups = (
        (context.advisory_decisions, "advisory decision(s) are non-binding and require explicit review"),
        (context.active_exceptions, "active exception(s) affect this scope"),
        (context.rejected_outcomes, "rejected outcome(s) affect this scope"),
        (context.unresolved_debt, "unresolved design-debt record(s) affect this scope"),
        (context.stale_records, "stale record(s) affect this scope"),
    )
    for records, message in warning_groups:
        if records:
            warnings.append(f"{len(records)} {message}")
    if context.bounded:
        warnings.append(
            f"Scoped context was bounded at {max(1, min(max_records, 100))} of {context.total_available} records"
        )
    warnings = list(dict.fromkeys(warnings))

    status = "BLOCK" if blockers else "WARN" if warnings else "ALLOW"
    return {
        "status": status,
        "scope": {
            "product": context.product,
            "archetype": context.archetype,
            "surface": context.surface,
            "component": context.component,
        },
        "bindingDecisions": context.binding_decisions,
        "advisoryDecisions": context.advisory_decisions,
        "historicalDecisions": context.historical_decisions,
        "inheritedRules": context.inherited_rules,
        "activeExceptions": context.active_exceptions,
        "rejectedOutcomes": context.rejected_outcomes,
        "unresolvedDebt": context.unresolved_debt,
        "staleRecords": context.stale_records,
        "bounded": context.bounded,
        "totalAvailable": context.total_available,
        "blockers": blockers,
        "warnings": warnings,
        "audit": audit,
    }


def _audit_decision_lifecycle(
    decisions: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    revisions_by_id: dict[str, list[int]] = {}
    for item in decisions:
        decision_id = item.get("id")
        if not decision_id:
            continue
        try:
            revision = int(item.get("revision", 1))
        except (TypeError, ValueError):
            errors.append(f"{decision_id}: revision must be an integer")
            continue
        revisions_by_id.setdefault(decision_id, []).append(revision)
    for decision_id, revisions in revisions_by_id.items():
        ordered = sorted(revisions)
        if len(ordered) != len(set(ordered)):
            errors.append(f"{decision_id}: duplicate decision revision detected")
        expected = list(range(1, max(ordered, default=0) + 1))
        if ordered != expected:
            errors.append(f"{decision_id}: revisions must be contiguous from 1")

    latest = {item.get("id"): item for item in _latest_decision_revisions(decisions) if item.get("id")}
    latest_outcomes: dict[str, dict[str, Any]] = {}
    for outcome in outcomes:
        decision_id = outcome.get("decisionId")
        if decision_id:
            latest_outcomes[decision_id] = outcome

    for decision_id, decision in latest.items():
        status = decision.get("status")
        supersedes = decision.get("supersedes")
        proposed_target = decision.get("proposesSupersession")
        superseded_by = decision.get("supersededBy")
        if supersedes == decision_id or proposed_target == decision_id:
            errors.append(f"{decision_id}: decision cannot supersede itself")
        if status in {DecisionStatus.PROPOSED.value, DecisionStatus.EXPERIMENTAL.value, DecisionStatus.REJECTED.value} and supersedes:
            errors.append(f"{decision_id}: non-binding decision cannot supersede {supersedes}")
        if status not in {DecisionStatus.PROPOSED.value, DecisionStatus.EXPERIMENTAL.value} and proposed_target:
            errors.append(f"{decision_id}: only advisory decisions may propose supersession")
        if proposed_target and proposed_target not in latest:
            errors.append(f"{decision_id}: proposed supersession target not found: {proposed_target}")
        if status == DecisionStatus.ACCEPTED.value and supersedes:
            target = latest.get(supersedes)
            if target is None:
                errors.append(f"{decision_id}: supersession target not found: {supersedes}")
            elif target.get("status") != DecisionStatus.SUPERSEDED.value:
                errors.append(f"{decision_id}: supersession target {supersedes} is not superseded")
            elif target.get("supersededBy") != decision_id:
                errors.append(f"{decision_id}: supersession target {supersedes} does not point back to this decision")
        if status == DecisionStatus.SUPERSEDED.value:
            successor_id = superseded_by
            successor = latest.get(successor_id)
            if successor is None:
                errors.append(f"{decision_id}: superseding decision not found: {successor_id}")
            elif successor.get("status") != DecisionStatus.ACCEPTED.value:
                errors.append(f"{decision_id}: superseding decision {successor_id} is not accepted")
            elif successor.get("supersedes") != decision_id:
                errors.append(f"{decision_id}: superseding decision {successor_id} does not point back to this decision")
        elif superseded_by:
            errors.append(f"{decision_id}: only superseded decisions may declare supersededBy")
        latest_outcome = latest_outcomes.get(decision_id)
        if (
            status == DecisionStatus.ACCEPTED.value
            and latest_outcome
            and latest_outcome.get("result") == OutcomeResult.REJECTED.value
        ):
            errors.append(
                f"{decision_id}: accepted decision has a later rejected outcome; append a deprecated, rejected, or superseded revision"
            )

    errors.extend(_audit_supersession_cycles(latest))
    return errors


def _audit_supersession_cycles(latest: dict[str, dict[str, Any]]) -> list[str]:
    graph = {
        decision_id: decision.get("supersedes")
        for decision_id, decision in latest.items()
        if decision.get("supersedes")
    }
    errors: list[str] = []
    completed: set[str] = set()
    for start in sorted(graph):
        if start in completed:
            continue
        path: list[str] = []
        positions: dict[str, int] = {}
        current: str | None = start
        while current in graph and current not in completed:
            if current in positions:
                cycle = path[positions[current]:] + [current]
                errors.append("Supersession cycle detected: " + " -> ".join(cycle))
                break
            positions[current] = len(path)
            path.append(current)
            current = graph[current]
        completed.update(path)
    return errors


def _audit_source_authorities(repository_root: Path, rules: dict[str, Any]) -> list[str]:
    mode = rules.get("authorityMode")
    sources = rules.get("sourceAuthorities", [])
    if mode is None and not sources:
        return []

    errors: list[str] = []
    if mode != "index-only":
        errors.append("product-rules authorityMode must be index-only when sourceAuthorities are declared")
    if not isinstance(sources, list) or not sources:
        return [*errors, "index-only product rules require sourceAuthorities"]

    indexed_paths: set[str] = set()
    for index, source in enumerate(sources):
        label = f"sourceAuthorities[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{label} must be an object")
            continue
        relative = source.get("path")
        expected = source.get("sha256")
        if not relative or not expected or not source.get("role"):
            errors.append(f"{label} requires path, sha256, and role")
            continue
        relative = Path(str(relative)).as_posix()
        if relative.startswith(".design/memory/"):
            errors.append(f"{label} cannot make memory its own source authority: {relative}")
            continue
        if relative in indexed_paths:
            errors.append(f"Duplicate source authority path: {relative}")
            continue
        indexed_paths.add(relative)
        if not isinstance(expected, str) or len(expected) != 64 or any(
            character not in "0123456789abcdef" for character in expected
        ):
            errors.append(f"{label}.sha256 must be a lowercase SHA-256 digest")
            continue
        try:
            path = ensure_within(repository_root, relative)
        except ValueError as error:
            errors.append(f"{label}: {error}")
            continue
        if not path.is_file():
            errors.append(f"Source authority is missing: {relative}")
        elif sha256_file(path) != expected:
            errors.append(f"Source authority hash mismatch: {relative}")

    if mode == "index-only":
        for rule in _iter_rules(rules):
            source = rule.get("sourceAuthority")
            if not source:
                errors.append(f"Indexed rule {rule.get('id', '<unknown>')} requires sourceAuthority")
            elif source not in indexed_paths:
                errors.append(
                    f"Indexed rule {rule.get('id', '<unknown>')} references an unbound authority: {source}"
                )
    return errors


def _iter_rules(rules: dict[str, Any]):
    yield from rules.get("portfolio", [])
    for values in rules.get("archetypes", {}).values():
        yield from values
    for product in rules.get("products", {}).values():
        yield from product.get("rules", [])


def _resolve_rules(rules: dict[str, Any], product: str | None, archetype: str | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    inherited: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    inherited.extend({**item, "authorityLevel": "portfolio"} for item in rules.get("portfolio", []))
    inherited.extend(
        {**item, "authorityLevel": "archetype", "archetype": archetype}
        for item in rules.get("archetypes", {}).get(archetype or "", [])
    )
    product_rules = rules.get("products", {}).get((product or "").lower(), {}).get("rules", [])
    for item in product_rules:
        override = item.get("overrides")
        broader = next((rule for rule in inherited if rule.get("id") == override), None)
        if broader and (broader.get("protected") or broader.get("category") in PROTECTED_CATEGORIES):
            conflicts.append({"ruleId": item.get("id"), "protectedRuleId": override})
            continue
        inherited.append({**item, "authorityLevel": "product", "product": product})
    return inherited, conflicts


def _matches_scope(
    item: dict[str, Any],
    product: str | None,
    archetype: str | None,
    surface: str | None,
    component: str | None,
    *,
    include_descendants: bool = False,
) -> bool:
    pairs = (("product", product), ("archetype", archetype), ("surface", surface), ("component", component))
    for key, requested in pairs:
        scoped = item.get(key)
        if scoped:
            if requested and str(scoped).lower() != str(requested).lower():
                return False
            if not requested and not include_descendants:
                return False
    return True


def _latest_decision_revisions(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        current = latest.get(record.get("id"))
        if current is None or _revision_number(record) > _revision_number(current):
            latest[record.get("id")] = record
    return list(latest.values())


def _next_revision(records: list[dict[str, Any]], decision_id: str) -> int:
    revisions = [_revision_number(item) for item in records if item.get("id") == decision_id]
    return max(revisions, default=0) + 1


def _revision_number(record: dict[str, Any]) -> int:
    try:
        return int(record.get("revision", 1))
    except (TypeError, ValueError):
        return 0


def _product_archetype(rules: dict[str, Any], product: str | None) -> str | None:
    if not product:
        return None
    return rules.get("products", {}).get(product.lower(), {}).get("archetype")


def _take(items: list[dict[str, Any]], budget: int) -> tuple[list[dict[str, Any]], int]:
    selected = items[:budget]
    return selected, max(0, budget - len(selected))


def _validate_iso_datetime(value: Any, field: str, errors: list[str]) -> None:
    if not value:
        return
    try:
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field} must be an ISO-8601 datetime")


def _validate_iso_date(value: Any, field: str, errors: list[str]) -> None:
    if not value:
        return
    try:
        date.fromisoformat(str(value))
    except ValueError:
        errors.append(f"{field} must be an ISO-8601 date")


def _date_before(value: str, today: date) -> bool:
    try:
        return date.fromisoformat(value) < today
    except (TypeError, ValueError):
        return False


def _date_on_or_after(value: str, today: date) -> bool:
    try:
        return date.fromisoformat(value) >= today
    except (TypeError, ValueError):
        return False


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
