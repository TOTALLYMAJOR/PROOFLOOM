from __future__ import annotations

import json
from datetime import date, datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any

from .models import AuthorityLevel, DecisionStatus, MemoryContext, OutcomeResult
from .repository import inspect_repository
from .storage import append_jsonl, atomic_write_json, read_json, read_jsonl


MEMORY_FILES = {
    "decisions": "decisions.jsonl",
    "outcomes": "outcomes.jsonl",
    "exceptions": "exceptions.jsonl",
    "debt": "debt.jsonl",
    "registry": "component-registry.json",
    "rules": "product-rules.json",
}

PROTECTED_CATEGORIES = {"accessibility", "safety", "semantic-correctness", "product-requirement"}
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


def initialize_memory(repository_root: str | Path, allow_existing_authority: bool = False) -> dict[str, Any]:
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
        "baseline-review-request.schema.json",
        "repair-plan.schema.json",
        "validation-evidence.schema.json",
    ):
        schema_path = schema_root / schema_name
        if not schema_path.exists():
            atomic_write_json(schema_path, json.loads(schema_source.joinpath(schema_name).read_text(encoding="utf-8")))
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
    return {
        "status": "READY",
        "root": str(destination),
        "files": sorted(str(path.relative_to(root)) for path in destination.iterdir()),
        "integratedExistingAuthority": bool(competing),
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
        elif outcomes is not None and not any(item.get("id") == promotion["outcomeId"] for item in outcomes):
            errors.append(f"Promotion outcome not found: {promotion['outcomeId']}")
        if level in {AuthorityLevel.PORTFOLIO, AuthorityLevel.ARCHETYPE, AuthorityLevel.PRODUCT}:
            if authorized_by == "quality-gate" or authorized_by.startswith("agent") or not authorized_by:
                errors.append("Portfolio, archetype, and product law promotion requires explicit human authority")
        elif not authorized_by:
            errors.append("Accepted local decisions require promotion.authorizedBy")
    if decision.get("category") in PROTECTED_CATEGORIES and decision.get("overrides"):
        errors.append("Protected categories cannot override broader rules")
    if existing is not None:
        prior = [item for item in existing if item.get("id") == decision.get("id")]
        if prior:
            expected = max(int(item.get("revision", 1)) for item in prior) + 1
            if int(decision.get("revision", expected)) != expected:
                errors.append(f"Revision for {decision.get('id')} must be {expected}")
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
) -> MemoryContext:
    root = memory_root(repository_root)
    max_records = max(1, min(max_records, 100))
    today = as_of or date.today()
    rules = read_json(root / MEMORY_FILES["rules"], {}) or {}
    resolved_archetype = archetype or _product_archetype(rules, product)
    inherited, conflicts = _resolve_rules(rules, product, resolved_archetype)
    decisions = _latest_decision_revisions(read_jsonl(root / MEMORY_FILES["decisions"]))
    relevant_decisions = [item for item in decisions if _matches_scope(item, product, resolved_archetype, surface, component)]
    relevant_decisions.sort(key=lambda item: (AUTHORITY_ORDER.get(item.get("authorityLevel", "portfolio"), 0), item.get("createdAt", "")))
    exceptions = [
        item
        for item in read_jsonl(root / MEMORY_FILES["exceptions"])
        if _matches_scope(item.get("scope", {}), product, resolved_archetype, surface, component)
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
        if item.get("result") == "rejected" and _matches_scope(item, product, resolved_archetype, surface, component)
    ]
    debt = [
        item
        for item in read_jsonl(root / MEMORY_FILES["debt"])
        if item.get("status") == "open" and _matches_scope(item.get("scope", {}), product, resolved_archetype, surface, component)
    ]
    stale = find_stale_records(repository_root, as_of=today)
    total = len(relevant_decisions) + len(active_exceptions) + len(outcomes) + len(debt) + len(stale)
    budget = max_records
    selected_decisions, budget = _take(relevant_decisions, budget)
    selected_exceptions, budget = _take(active_exceptions, budget)
    selected_outcomes, budget = _take(outcomes, budget)
    selected_debt, budget = _take(debt, budget)
    selected_stale, _ = _take(stale, budget)
    return MemoryContext(
        product=product,
        archetype=resolved_archetype,
        surface=surface,
        component=component,
        inherited_rules=inherited,
        decisions=selected_decisions,
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
    root = memory_root(repository_root)
    errors: list[str] = []
    warnings: list[str] = []
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
        errors.extend(f"{item.get('id', '<unknown>')}: {error}" for error in validate_decision(item, None, outcomes))
    for item in exceptions:
        errors.extend(f"{item.get('id', '<unknown>')}: {error}" for error in validate_exception(item))
    stale = find_stale_records(repository_root, as_of)
    if stale:
        warnings.append(f"{len(stale)} stale or expired record(s) require review")
    context = retrieve_context(repository_root, max_records=100, as_of=as_of)
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
) -> bool:
    pairs = (("product", product), ("archetype", archetype), ("surface", surface), ("component", component))
    for key, requested in pairs:
        scoped = item.get(key)
        if scoped and (not requested or str(scoped).lower() != str(requested).lower()):
            return False
    return True


def _latest_decision_revisions(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        current = latest.get(record.get("id"))
        if current is None or int(record.get("revision", 1)) > int(current.get("revision", 1)):
            latest[record.get("id")] = record
    return list(latest.values())


def _next_revision(records: list[dict[str, Any]], decision_id: str) -> int:
    revisions = [int(item.get("revision", 1)) for item in records if item.get("id") == decision_id]
    return max(revisions, default=0) + 1


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
