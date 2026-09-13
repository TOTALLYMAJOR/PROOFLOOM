from __future__ import annotations

import fnmatch
import json
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any, Iterable

from .storage import ensure_within, read_json, sha256_file


TERMINAL_BACKLOG_STATUSES = {"COMPLETED", "CANCELLED", "DEFERRED_WITH_AUTHORITY"}
OPEN_BACKLOG_STATUSES = {"ACTIVE", "BLOCKED", "STAGED"}
BACKLOG_STATUSES = TERMINAL_BACKLOG_STATUSES | OPEN_BACKLOG_STATUSES
RISK_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
VENDOR_MARKERS = ("openai", "anthropic", "claude", "gemini", "gpt-", "llama", "mistral")


def load_industry_standards() -> dict[str, Any]:
    source = files("design_intelligence").joinpath("data/defaults/industry-standards.json")
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Industry standards catalog must contain an object")
    return payload


def audit_planes(
    repository_root: str | Path,
    manifest: dict[str, Any],
    *,
    today: date | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    planes = manifest.get("spec", {}).get("planes", {})
    observed = today or datetime.now(timezone.utc).date()
    intent = audit_intent_plane(root, planes.get("intent", {}), today=observed)
    architecture = audit_architecture_plane(
        root,
        planes.get("architecture", {}),
        available_commands=set(
            manifest.get("spec", {}).get("verification", {}).get("commands", {})
        ),
        today=observed,
    )
    intelligence = audit_intelligence_plane(root, planes.get("intelligence", {}))
    statuses = [intent["status"], architecture["status"], intelligence["status"]]
    status = "FAIL" if "FAIL" in statuses else "WARN" if "WARN" in statuses else "PASS"
    return {
        "status": status,
        "observedAt": observed.isoformat(),
        "intent": intent,
        "architecture": architecture,
        "intelligence": intelligence,
        "certificationClaimed": False,
    }


def audit_intent_plane(
    repository_root: str | Path,
    config: dict[str, Any],
    *,
    today: date | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    if not config.get("enabled"):
        return _disabled("intent")
    errors: list[str] = []
    warnings: list[str] = []
    index = _load_configured_json(root, config.get("index"), "intent index", errors)
    backlog = audit_backlog(root, config.get("backlog", {}))
    if errors or not isinstance(index, dict):
        return {
            "status": "FAIL",
            "enabled": True,
            "counts": {},
            "backlog": backlog,
            "errors": errors,
            "warnings": warnings,
        }

    if index.get("schemaVersion") != 1:
        errors.append("intent index schemaVersion must be 1")
    observed = today or datetime.now(timezone.utc).date()
    max_age = config.get("maxReviewAgeDays", 180)
    records_by_kind: dict[str, list[dict[str, Any]]] = {}
    for kind in (
        "vision",
        "principles",
        "personas",
        "requirements",
        "journeys",
        "successMetrics",
        "constraints",
        "experiments",
    ):
        value = index.get(kind, [])
        if not isinstance(value, list):
            errors.append(f"intent.{kind} must be an array")
            records_by_kind[kind] = []
            continue
        records = [record for record in value if isinstance(record, dict)]
        if len(records) != len(value):
            errors.append(f"intent.{kind} must contain only objects")
        records_by_kind[kind] = records

    all_ids: set[str] = set()
    for kind, records in records_by_kind.items():
        for record in records:
            identifier = record.get("id")
            if not isinstance(identifier, str) or not identifier:
                errors.append(f"intent.{kind} record is missing id")
                continue
            if identifier in all_ids:
                errors.append(f"Duplicate intent id: {identifier}")
            all_ids.add(identifier)
            _audit_source_binding(root, record.get("source"), f"intent.{kind}.{identifier}", errors)
            if record.get("status", "ACTIVE") == "ACTIVE":
                _audit_review_date(
                    record.get("lastReviewed"),
                    max_age,
                    observed,
                    f"intent.{kind}.{identifier}",
                    errors,
                )

    persona_ids = _ids(records_by_kind["personas"])
    requirement_ids = _ids(records_by_kind["requirements"])
    journey_ids = _ids(records_by_kind["journeys"])
    metric_ids = _ids(records_by_kind["successMetrics"])
    experiment_ids = _ids(records_by_kind["experiments"])

    active_journeys = [item for item in records_by_kind["journeys"] if item.get("status", "ACTIVE") == "ACTIVE"]
    journey_requirement_links: set[str] = set()
    journey_metric_links: set[str] = set()
    journey_test_count = 0
    for journey in active_journeys:
        identifier = journey.get("id", "unknown")
        for field in ("owner", "startingState", "successState"):
            if not isinstance(journey.get(field), str) or not journey[field].strip():
                errors.append(f"journey {identifier} requires {field}")
        personas = _string_list(journey.get("personas"), f"journey {identifier}.personas", errors, required=True)
        requirements = _string_list(
            journey.get("requirements"), f"journey {identifier}.requirements", errors, required=True
        )
        tests = _string_list(journey.get("tests"), f"journey {identifier}.tests", errors, required=True)
        metrics = _string_list(journey.get("metrics"), f"journey {identifier}.metrics", errors, required=True)
        _check_refs(personas, persona_ids, f"journey {identifier} persona", errors)
        _check_refs(requirements, requirement_ids, f"journey {identifier} requirement", errors)
        _check_refs(metrics, metric_ids, f"journey {identifier} metric", errors)
        journey_requirement_links.update(requirements)
        journey_metric_links.update(metrics)
        for test_path in tests:
            _audit_file(root, test_path, f"journey {identifier} test", errors)
            journey_test_count += 1

    active_requirements = [
        item for item in records_by_kind["requirements"] if item.get("status", "ACTIVE") == "ACTIVE"
    ]
    for requirement in active_requirements:
        identifier = requirement.get("id", "unknown")
        journeys = _string_list(
            requirement.get("journeys"), f"requirement {identifier}.journeys", errors, required=True
        )
        metrics = _string_list(
            requirement.get("successMetrics"),
            f"requirement {identifier}.successMetrics",
            errors,
            required=True,
        )
        _check_refs(journeys, journey_ids, f"requirement {identifier} journey", errors)
        _check_refs(metrics, metric_ids, f"requirement {identifier} metric", errors)
        if identifier not in journey_requirement_links:
            errors.append(f"Active requirement has no reciprocal journey coverage: {identifier}")

    for experiment in records_by_kind["experiments"]:
        identifier = experiment.get("id", "unknown")
        _check_refs(
            _string_list(experiment.get("metrics"), f"experiment {identifier}.metrics", errors),
            metric_ids,
            f"experiment {identifier} metric",
            errors,
        )
    for metric in metric_ids - journey_metric_links:
        warnings.append(f"Success metric is not linked to an active journey: {metric}")
    for experiment in experiment_ids:
        if not any(experiment == item.get("id") for item in records_by_kind["experiments"]):
            errors.append(f"Experiment is not resolvable: {experiment}")

    statuses = ["FAIL" if errors else "PASS", backlog["status"]]
    status = "FAIL" if "FAIL" in statuses else "WARN" if warnings or "WARN" in statuses else "PASS"
    return {
        "status": status,
        "enabled": True,
        "index": config.get("index"),
        "counts": {kind: len(records) for kind, records in records_by_kind.items()},
        "journeyCoverage": {
            "activeJourneys": len(active_journeys),
            "activeRequirements": len(active_requirements),
            "journeyTests": journey_test_count,
            "orphanRequirements": sorted(requirement_ids - journey_requirement_links),
        },
        "backlog": backlog,
        "errors": errors + backlog.get("errors", []),
        "warnings": warnings + backlog.get("warnings", []),
    }


def audit_architecture_plane(
    repository_root: str | Path,
    config: dict[str, Any],
    *,
    available_commands: set[str] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    if not config.get("enabled"):
        return _disabled("architecture")
    errors: list[str] = []
    warnings: list[str] = []
    profile = _load_configured_json(root, config.get("standardsProfile"), "standards profile", errors)
    catalog = load_industry_standards()
    if errors or not isinstance(profile, dict):
        return {
            "status": "FAIL",
            "enabled": True,
            "standards": [],
            "errors": errors,
            "warnings": warnings,
            "certificationClaimed": False,
        }
    if profile.get("schemaVersion") != 1:
        errors.append("standards profile schemaVersion must be 1")
    if profile.get("catalogVersion") != catalog.get("catalogVersion"):
        errors.append(
            f"Standards profile catalogVersion must be {catalog.get('catalogVersion')}"
        )
    observed = today or datetime.now(timezone.utc).date()
    _audit_deadline(catalog.get("reviewAfter"), observed, "industry standards catalog", errors)
    _audit_review_date(
        profile.get("reviewedAt"),
        config.get("maxReviewAgeDays", 90),
        observed,
        "standards profile",
        errors,
    )
    _audit_deadline(profile.get("reviewAfter"), observed, "standards profile", errors)
    authority_paths = _string_list(
        config.get("authorityPaths"), "architecture authorityPaths", errors, required=True
    )
    contract_paths = _string_list(
        config.get("contractPaths"), "architecture contractPaths", errors, required=True
    )
    adr_globs = _string_list(config.get("adrGlobs"), "architecture adrGlobs", errors, required=True)
    boundary_checks = _string_list(
        config.get("boundaryChecks"), "architecture boundaryChecks", errors, required=True
    )
    for path in authority_paths:
        _audit_file(root, path, "architecture authority", errors)
    for path in contract_paths:
        _audit_file(root, path, "architecture contract", errors)
    adr_paths: set[str] = set()
    for pattern in adr_globs:
        if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
            errors.append(f"Architecture ADR glob must remain repository-relative: {pattern}")
            continue
        matches = [path for path in root.glob(pattern) if path.is_file()]
        if not matches:
            errors.append(f"Architecture ADR glob matched no records: {pattern}")
        adr_paths.update(path.relative_to(root).as_posix() for path in matches)
    if available_commands is not None:
        for command in boundary_checks:
            if command not in available_commands:
                errors.append(f"Architecture boundary check is not declared: {command}")

    technology = config.get("technologyCurrency")
    technology_manifests: list[str] = []
    if not isinstance(technology, dict):
        errors.append("architecture technologyCurrency must be an object")
    else:
        if technology.get("policy") != "contextual-not-latest":
            errors.append("Technology currency policy must be contextual-not-latest")
        _audit_review_date(
            technology.get("reviewedAt"),
            config.get("maxReviewAgeDays", 90),
            observed,
            "technology currency",
            errors,
        )
        _audit_deadline(
            technology.get("reviewAfter"), observed, "technology currency", errors
        )
        technology_manifests = _string_list(
            technology.get("manifests"),
            "technology currency manifests",
            errors,
            required=True,
        )
        technology_evidence = _string_list(
            technology.get("evidence"),
            "technology currency evidence",
            errors,
            required=True,
        )
        for path in technology_manifests:
            _audit_file(root, path, "technology manifest", errors)
        for path in technology_evidence:
            _audit_file(root, path, "technology currency evidence", errors)
    contexts = set(_string_list(profile.get("contexts"), "standards profile contexts", errors, required=True))
    catalog_entries = {
        item["id"]: item for item in catalog.get("standards", []) if isinstance(item, dict) and item.get("id")
    }
    profile_entries = {
        item["id"]: item for item in profile.get("standards", []) if isinstance(item, dict) and item.get("id")
    }
    if len(profile_entries) != len(profile.get("standards", [])):
        errors.append("Standards profile contains duplicate or invalid standard entries")

    results: list[dict[str, Any]] = []
    for identifier, standard in catalog_entries.items():
        applicable = bool(contexts.intersection(standard.get("contexts", [])))
        official_url = standard.get("officialUrl")
        if not isinstance(official_url, str) or not official_url.startswith("https://"):
            errors.append(f"Standard requires an official HTTPS source: {identifier}")
        entry = profile_entries.get(identifier)
        if not entry:
            if applicable:
                errors.append(f"Applicable standard is missing from profile: {identifier}")
            continue
        version_current = entry.get("version") == standard.get("version")
        if not version_current:
            errors.append(
                f"Standard version is stale for {identifier}: expected {standard.get('version')}, got {entry.get('version')}"
            )
        declared_applicable = entry.get("applicability") == "APPLICABLE"
        if declared_applicable != applicable:
            errors.append(
                f"Standard applicability mismatch for {identifier}: catalog={applicable}, profile={declared_applicable}"
            )
        disposition = entry.get("disposition")
        if disposition not in {"ADOPTED", "TAILORED", "NOT_APPLICABLE", "GAP"}:
            errors.append(f"Invalid standards disposition for {identifier}: {disposition}")
        if applicable and disposition == "NOT_APPLICABLE":
            errors.append(f"Applicable standard cannot be NOT_APPLICABLE: {identifier}")
        if not applicable and disposition != "NOT_APPLICABLE":
            errors.append(f"Non-applicable standard must be NOT_APPLICABLE: {identifier}")
        if disposition == "GAP":
            errors.append(f"Unresolved industry-standard gap: {identifier}")
        if not isinstance(entry.get("rationale"), str) or not entry["rationale"].strip():
            errors.append(f"Standard profile entry requires rationale: {identifier}")
        evidence = _string_list(entry.get("evidence"), f"standard {identifier}.evidence", errors)
        if applicable and disposition in {"ADOPTED", "TAILORED"} and not evidence:
            errors.append(f"Applicable standard requires repository evidence: {identifier}")
        for path in evidence:
            _audit_file(root, path, f"standard {identifier} evidence", errors)
        results.append({
            "id": identifier,
            "title": standard.get("title"),
            "officialUrl": standard.get("officialUrl"),
            "version": standard.get("version"),
            "applicable": applicable,
            "disposition": disposition,
            "versionCurrent": version_current,
        })
    unknown = sorted(set(profile_entries) - set(catalog_entries))
    errors.extend(f"Unknown standard in profile: {identifier}" for identifier in unknown)
    return {
        "status": "PASS" if not errors else "FAIL",
        "enabled": True,
        "profile": config.get("standardsProfile"),
        "catalogVersion": catalog.get("catalogVersion"),
        "reviewAfter": profile.get("reviewAfter"),
        "contexts": sorted(contexts),
        "repositoryArchitecture": {
            "authorityCount": len(authority_paths),
            "contractCount": len(contract_paths),
            "adrCount": len(adr_paths),
            "boundaryChecks": boundary_checks,
            "technologyManifests": technology_manifests,
            "technologyPolicy": technology.get("policy") if isinstance(technology, dict) else None,
        },
        "standards": results,
        "errors": errors,
        "warnings": warnings,
        "certificationClaimed": False,
    }


def audit_intelligence_plane(repository_root: str | Path, config: dict[str, Any]) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    if not config.get("enabled"):
        return _disabled("intelligence")
    errors: list[str] = []
    warnings: list[str] = []
    policy = _load_configured_json(root, config.get("routingPolicy"), "model routing policy", errors)
    instruction_paths = _string_list(config.get("instructionPaths"), "instructionPaths", errors, required=True)
    skill_roots = _string_list(config.get("skillRoots"), "skillRoots", errors)
    role_paths = _string_list(config.get("rolePaths"), "rolePaths", errors)
    for path in instruction_paths:
        _audit_file(root, path, "instruction authority", errors)
    skill_files: list[str] = []
    for path in skill_roots:
        target = _safe_path(root, path, "skill root", errors)
        if target and not target.is_dir():
            errors.append(f"Skill root does not exist: {path}")
        elif target:
            skill_files.extend(
                item.relative_to(root).as_posix() for item in sorted(target.glob("*/SKILL.md"))
            )
    for path in role_paths:
        _audit_file(root, path, "role definition", errors)
    classes: list[dict[str, Any]] = []
    if isinstance(policy, dict):
        if policy.get("schemaVersion") != 1:
            errors.append("model routing policy schemaVersion must be 1")
        serialized = json.dumps(policy, sort_keys=True).lower()
        for marker in VENDOR_MARKERS:
            if marker in serialized:
                errors.append(f"Routing policy must use capability classes, not vendor binding: {marker}")
        raw_classes = policy.get("capabilityClasses", [])
        if not isinstance(raw_classes, list) or not raw_classes:
            errors.append("Routing policy requires capabilityClasses")
        else:
            ids: set[str] = set()
            priorities: set[int] = set()
            for item in raw_classes:
                if not isinstance(item, dict):
                    errors.append("Routing capability classes must be objects")
                    continue
                identifier = item.get("id")
                if not isinstance(identifier, str) or not identifier:
                    errors.append("Routing capability class requires id")
                    continue
                if identifier in ids:
                    errors.append(f"Duplicate routing capability class: {identifier}")
                ids.add(identifier)
                priority = item.get("priority")
                if not isinstance(priority, int) or priority < 1:
                    errors.append(f"Routing capability class requires positive priority: {identifier}")
                elif priority in priorities:
                    errors.append(f"Routing capability class priority must be unique: {priority}")
                else:
                    priorities.add(priority)
                if item.get("maxRisk") not in RISK_RANK:
                    errors.append(f"Routing capability class has invalid maxRisk: {identifier}")
                _string_list(item.get("capabilities"), f"routing class {identifier}.capabilities", errors, required=True)
                _string_list(item.get("workTypes"), f"routing class {identifier}.workTypes", errors, required=True)
                classes.append(item)
        authority = policy.get("authority", {})
        if not isinstance(authority, dict):
            errors.append("Routing policy authority must be an object")
        else:
            for boundary in (
                "majorProductDecision",
                "architectureBoundaryChange",
                "securityPolicyChange",
                "productionWrite",
                "baselineMutation",
            ):
                if authority.get(boundary) != "HUMAN_APPROVAL_REQUIRED":
                    errors.append(f"Routing authority must fail closed for {boundary}")
    return {
        "status": "PASS" if not errors else "FAIL",
        "enabled": True,
        "routingPolicy": config.get("routingPolicy"),
        "instructionCount": len(instruction_paths),
        "skillCount": len(skill_files),
        "roleCount": len(role_paths),
        "capabilityClassCount": len(classes),
        "vendorNeutral": not any("vendor binding" in error for error in errors),
        "errors": errors,
        "warnings": warnings,
    }


def audit_backlog(repository_root: str | Path, config: dict[str, Any]) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    if config.get("completionPolicy") != "all-terminal":
        errors.append("Backlog completionPolicy must be all-terminal")
    terminal_statuses = config.get("terminalStatuses")
    if not isinstance(terminal_statuses, list) or not all(
        isinstance(item, str) for item in terminal_statuses
    ) or set(terminal_statuses) != TERMINAL_BACKLOG_STATUSES:
        errors.append("Backlog terminalStatuses cannot weaken the governed terminal set")
    sources = config.get("sources", [])
    if not isinstance(sources, list) or not sources:
        return {
            "status": "FAIL",
            "completion": "UNKNOWN",
            "items": [],
            "waves": [],
            "errors": ["Backlog requires at least one declared source"],
            "warnings": [],
        }
    items: list[dict[str, Any]] = []
    for source_index, source in enumerate(sources):
        if not isinstance(source, dict):
            errors.append(f"Backlog source {source_index} must be an object")
            continue
        path = source.get("path")
        parser = source.get("parser")
        role = source.get("role", "active")
        include = source.get("includeInCompletion", role != "historical")
        target = _safe_path(root, path, f"backlog source {source_index}", errors)
        if target is None or not target.exists():
            errors.append(f"Backlog source does not exist: {path}")
            continue
        try:
            parsed = _parse_backlog_source(root, target, parser, source)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"Unable to parse backlog source {path}: {error}")
            continue
        if source.get("requireItems", True) and not parsed:
            errors.append(f"Backlog source produced no items: {path}")
        for item in parsed:
            if role == "staged" and item.get("status") == "ACTIVE":
                item["status"] = "STAGED"
            item.update({
                "source": target.relative_to(root).as_posix(),
                "sourceRole": role,
                "includeInCompletion": bool(include),
            })
            items.append(item)

    configured_source_paths = {
        source.get("path") for source in sources if isinstance(source, dict)
    }
    source_items: dict[str, set[str]] = defaultdict(set)
    for item in items:
        if item.get("id"):
            source_items[item["source"]].add(item["id"])
    source_config = {
        source.get("path"): source for source in sources if isinstance(source, dict)
    }
    shadowed_records: list[dict[str, str]] = []
    filtered_items: list[dict[str, Any]] = []
    for item in items:
        shadowed_by = source_config.get(item["source"], {}).get("shadowedBy")
        if shadowed_by:
            if shadowed_by not in configured_source_paths:
                errors.append(
                    f"Backlog source shadowedBy is not declared: {item['source']} -> {shadowed_by}"
                )
            elif item.get("id") in source_items.get(shadowed_by, set()):
                shadowed_records.append({
                    "id": item["id"],
                    "source": item["source"],
                    "shadowedBy": shadowed_by,
                })
                continue
        filtered_items.append(item)
    items = filtered_items

    active_items = [item for item in items if item["includeInCompletion"]]
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in active_items:
        by_id[item.get("id", "")].append(item)
        status = item.get("status")
        if status not in BACKLOG_STATUSES:
            errors.append(f"Unknown backlog status for {item.get('id')}: {status}")
        if status in {"CANCELLED", "DEFERRED_WITH_AUTHORITY"}:
            if not item.get("authority") or not item.get("rationale"):
                errors.append(
                    f"Terminal disposition requires authority and rationale: {item.get('id')}"
                )
        if status == "COMPLETED" and not item.get("evidence"):
            errors.append(f"Completed backlog item requires evidence: {item.get('id')}")
        if status == "COMPLETED" and item.get("evidenceMustExist"):
            for evidence_path in item.get("evidence", []):
                target = _safe_path(
                    root,
                    evidence_path,
                    f"backlog {item.get('id')} evidence",
                    errors,
                )
                if target and not target.is_file():
                    errors.append(
                        f"Completed backlog evidence does not exist: {item.get('id')} -> {evidence_path}"
                    )
    for identifier, duplicates in by_id.items():
        if not identifier:
            errors.append("Backlog item is missing id")
        elif len(duplicates) > 1:
            errors.append(f"Duplicate backlog item across active sources: {identifier}")

    dependencies: dict[str, list[str]] = {}
    config_dependencies = config.get("dependencies", {})
    for item in active_items:
        identifier = item.get("id")
        if not identifier:
            continue
        item_dependencies = _string_list(
            item.get("dependencies", []),
            f"backlog {identifier}.dependencies",
            errors,
        )
        configured_dependencies = _string_list(
            config_dependencies.get(identifier, []),
            f"backlog {identifier}.configuredDependencies",
            errors,
        )
        dependencies[identifier] = list(
            dict.fromkeys(item_dependencies + configured_dependencies)
        )
        item["dependencies"] = dependencies[identifier]
        for dependency in dependencies[identifier]:
            if dependency not in by_id:
                errors.append(f"Backlog dependency is not inventoried: {identifier} -> {dependency}")
    cycle = _dependency_cycle(dependencies)
    if cycle:
        errors.append("Backlog dependency cycle: " + " -> ".join(cycle))

    waves = _backlog_waves(active_items, dependencies) if not cycle else []
    terminal = [item for item in active_items if item.get("status") in TERMINAL_BACKLOG_STATUSES]
    completion = "COMPLETE" if active_items and len(terminal) == len(active_items) and not errors else "IN_PROGRESS"
    if not active_items:
        completion = "EMPTY"
        warnings.append("No completion-governed backlog items were discovered")
    return {
        "status": "PASS" if not errors else "FAIL",
        "completion": completion,
        "completionPolicy": config.get("completionPolicy", "all-terminal"),
        "sourceCount": len(sources),
        "itemCount": len(active_items),
        "historicalItemCount": len(items) - len(active_items),
        "terminalCount": len(terminal),
        "openCount": len(active_items) - len(terminal),
        "items": [
            _public_backlog_item(item)
            for item in sorted(active_items, key=lambda item: item.get("id", ""))
        ],
        "shadowedRecords": sorted(
            shadowed_records,
            key=lambda item: (item["id"], item["source"]),
        ),
        "waves": waves,
        "errors": errors,
        "warnings": warnings,
    }


def route_task(
    repository_root: str | Path,
    manifest: dict[str, Any],
    task: dict[str, Any],
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    config = manifest.get("spec", {}).get("planes", {}).get("intelligence", {})
    if not config.get("enabled"):
        return {
            "status": "WARN",
            "taskId": task.get("id"),
            "capabilityClass": None,
            "humanApprovalRequired": True,
            "vendorSelected": False,
            "errors": [],
            "warnings": ["Intelligence routing is not configured"],
        }
    errors: list[str] = []
    policy = _load_configured_json(root, config.get("routingPolicy"), "model routing policy", errors)
    if errors or not isinstance(policy, dict):
        return {"status": "FAIL", "taskId": task.get("id"), "errors": errors}
    required = set(task.get("requiredCapabilities", []))
    work_type = task.get("workType")
    risk = task.get("risk")
    candidates: list[dict[str, Any]] = []
    for capability_class in policy.get("capabilityClasses", []):
        if work_type not in capability_class.get("workTypes", []):
            continue
        if not required.issubset(set(capability_class.get("capabilities", []))):
            continue
        if RISK_RANK.get(risk, 99) > RISK_RANK.get(capability_class.get("maxRisk"), 0):
            continue
        candidates.append(capability_class)
    candidates.sort(key=lambda item: item["priority"])
    if not candidates:
        return {
            "status": "FAIL",
            "taskId": task.get("id"),
            "workType": work_type,
            "risk": risk,
            "requiredCapabilities": sorted(required),
            "errors": ["No approved capability class satisfies task requirements"],
        }
    selected = candidates[0]
    human_approval = risk in {"high", "critical"} or bool(task.get("authorityBoundaries"))
    return {
        "status": "PASS",
        "taskId": task.get("id"),
        "workType": work_type,
        "risk": risk,
        "requiredCapabilities": sorted(required),
        "capabilityClass": selected["id"],
        "humanApprovalRequired": human_approval,
        "vendorSelected": False,
        "errors": [],
    }


def intent_context_paths(
    repository_root: str | Path,
    manifest: dict[str, Any],
    task: dict[str, Any],
) -> list[tuple[str, str]]:
    root = Path(repository_root).resolve()
    config = manifest.get("spec", {}).get("planes", {}).get("intent", {})
    if not config.get("enabled"):
        return []
    index = read_json(ensure_within(root, config["index"]), {}) or {}
    requested: set[str] = set()
    intent = task.get("intent", {})
    for field in ("requirements", "journeys", "successMetrics", "experiments"):
        requested.update(intent.get(field, []))
    paths: dict[str, list[str]] = defaultdict(list)
    for kind in ("requirements", "journeys", "successMetrics", "experiments"):
        for record in index.get(kind, []):
            if record.get("id") not in requested:
                continue
            source = record.get("source", {})
            if isinstance(source.get("path"), str):
                paths[source["path"]].append(record["id"])
    if isinstance(config.get("index"), str):
        paths[config["index"]].append("intent-index")
    return [
        (path, f"linked intent evidence: {', '.join(sorted(ids))}")
        for path, ids in sorted(paths.items())
    ]


def _parse_backlog_source(
    root: Path,
    target: Path,
    parser: Any,
    options: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if parser == "task-store":
        if not target.is_dir():
            raise ValueError("task-store parser requires a directory")
        records: list[dict[str, Any]] = []
        for path in sorted(target.glob("*/*.json")):
            packet = read_json(path, {}) or {}
            if not isinstance(packet, dict):
                raise ValueError(f"{path.relative_to(root)} must contain an object")
            folder = path.parent.name
            status = packet.get("status")
            if folder == "active" and status not in {"ACTIVE", "STAGED"}:
                raise ValueError(f"{path.relative_to(root)} status does not match active state folder")
            if folder == "blocked" and status != "BLOCKED":
                raise ValueError(f"{path.relative_to(root)} status does not match blocked state folder")
            if folder == "completed" and status not in TERMINAL_BACKLOG_STATUSES:
                raise ValueError(f"{path.relative_to(root)} status does not match completed state folder")
            records.append({
                "id": packet.get("id"),
                "title": packet.get("title"),
                "status": packet.get("status"),
                "dependencies": packet.get("dependencies", []),
                "authority": packet.get("terminalDisposition", {}).get("authority"),
                "rationale": packet.get("terminalDisposition", {}).get("rationale"),
                "evidence": packet.get("evidence", []),
                "evidenceMustExist": True,
            })
        return records
    if not target.is_file():
        raise ValueError(f"{parser} parser requires a file")
    text = target.read_text(encoding="utf-8")
    if parser == "markdown-checkboxes":
        return _parse_markdown_checkboxes(text)
    if parser == "markdown-headings":
        heading_levels = (options or {}).get("headingLevels")
        if heading_levels is not None and (
            not isinstance(heading_levels, list)
            or not heading_levels
            or not all(isinstance(level, int) and 1 <= level <= 6 for level in heading_levels)
        ):
            raise ValueError("markdown headingLevels must contain integers from 1 through 6")
        return _parse_markdown_headings(text, heading_levels=heading_levels)
    if parser == "json-items":
        payload = json.loads(text)
        values = payload.get("items") if isinstance(payload, dict) else payload
        if not isinstance(values, list):
            raise ValueError("json-items requires an array or an object with items")
        if not all(isinstance(item, dict) for item in values):
            raise ValueError("json-items contains an unparsed non-object item")
        return [dict(item) for item in values]
    raise ValueError(f"unsupported parser: {parser}")


def _parse_markdown_checkboxes(text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    pattern = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+([A-Z][A-Z0-9]+(?:-[A-Z0-9]+)+)\b\s*[:\-]?\s*(.*)$")
    for line in text.splitlines():
        match = pattern.match(line)
        if re.match(r"^\s*[-*]\s+\[[ xX]\]\s+", line) and not match:
            raise ValueError(f"unparsed checkbox backlog item: {line.strip()}")
        if not match:
            continue
        records.append({
            "id": match.group(2),
            "title": match.group(3).strip() or match.group(2),
            "status": "COMPLETED" if match.group(1).lower() == "x" else "ACTIVE",
            "dependencies": [],
            "evidence": ["declared complete in markdown"] if match.group(1).lower() == "x" else [],
        })
    return records


def _parse_markdown_headings(
    text: str,
    *,
    heading_levels: list[int] | None = None,
) -> list[dict[str, Any]]:
    identifier = r"([A-Z][A-Za-z0-9]+(?:-[A-Za-z0-9]+)+)"
    levels = sorted(set(heading_levels or range(1, 7)))
    heading_prefix = "(?:" + "|".join(f"#{{{level}}}" for level in levels) + ")"
    heading = re.compile(
        rf"^{heading_prefix}\s+(?:[^A-Z0-9\n]+\s*)?{identifier}\b\s*[:\-]?\s*(.*)$"
    )
    table_row = re.compile(rf"^\|\s*`?{identifier}`?\s*\|\s*(.*)$")
    section_heading = re.compile(r"^#{1,6}\s+(.+?)\s*$")
    status_line = re.compile(
        r"^\s*(?:[-*]\s*)?\*{0,2}(Status|Classification)\*{0,2}\s*:\s*(.+)$",
        re.I,
    )
    evidence_path = re.compile(
        r"`([^`]+\.(?:md|mdx|json|yaml|yml|ts|tsx|js|mjs|cjs|sql))`",
        re.I,
    )
    records: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_section = ""

    def finish_current() -> None:
        nonlocal current
        if not current:
            return
        section = str(current.pop("_section", "")).lower()
        if any(token in section for token in ("recently closed", "archived", "verification evidence")):
            current["status"] = "COMPLETED"
        current["evidence"] = list(dict.fromkeys(current.pop("_evidence", [])))
        records.append(current)
        current = None

    for line in text.splitlines():
        match = heading.match(line)
        table_match = table_row.match(line)
        if match:
            finish_current()
            current = {
                "id": match.group(1),
                "title": match.group(2).strip() or match.group(1),
                "status": "ACTIVE",
                "dependencies": [],
                "_evidence": [],
                "_section": current_section,
                "evidenceMustExist": True,
            }
            continue
        if table_match:
            finish_current()
            remainder = table_match.group(2).split("|", 1)[0].strip()
            current = {
                "id": table_match.group(1),
                "title": remainder or table_match.group(1),
                "status": "ACTIVE",
                "dependencies": [],
                "_evidence": [],
                "_section": current_section,
                "evidenceMustExist": True,
            }
            finish_current()
            continue
        section_match = section_heading.match(line)
        if section_match:
            finish_current()
            current_section = section_match.group(1).strip()
            continue
        if current:
            match = status_line.match(line)
            if match:
                classified = _normalize_backlog_status(match.group(2))
                if classified in BACKLOG_STATUSES:
                    current["status"] = classified
            if re.match(r"^\s*[-*]\s+Closed\b", line, re.I):
                current["status"] = "COMPLETED"
            current["_evidence"].extend(evidence_path.findall(line))
    finish_current()
    return records


def _normalize_backlog_status(value: str) -> str:
    normalized = re.sub(r"[^a-z]+", "_", value.lower()).strip("_")
    if "blocked" in normalized:
        return "BLOCKED"
    if "deferred" in normalized:
        return "STAGED"
    if "archive" in normalized or "closed" in normalized:
        return "COMPLETED"
    if normalized.startswith("staged") or normalized.startswith("planned"):
        return "STAGED"
    if normalized.startswith("cancelled") or normalized.startswith("canceled"):
        return "CANCELLED"
    if normalized in {"done", "complete", "completed", "closed"} or normalized.startswith("complete_"):
        return "COMPLETED"
    if normalized.startswith("active") or normalized.startswith("promoted"):
        return "ACTIVE"
    return {
        "done": "COMPLETED",
        "complete": "COMPLETED",
        "completed": "COMPLETED",
        "in_progress": "ACTIVE",
        "active": "ACTIVE",
        "open": "ACTIVE",
        "blocked": "BLOCKED",
        "staged": "STAGED",
        "planned": "STAGED",
        "cancelled": "CANCELLED",
        "canceled": "CANCELLED",
        "deferred_with_authority": "DEFERRED_WITH_AUTHORITY",
    }.get(normalized, normalized.upper())


def _backlog_waves(items: list[dict[str, Any]], dependencies: dict[str, list[str]]) -> list[dict[str, Any]]:
    by_id = {item["id"]: item for item in items if item.get("id")}
    terminal = {identifier for identifier, item in by_id.items() if item.get("status") in TERMINAL_BACKLOG_STATUSES}
    remaining = set(by_id) - terminal
    waves: list[dict[str, Any]] = []
    resolved = set(terminal)
    wave_number = 1
    while remaining:
        dependency_ready = sorted(
            identifier
            for identifier in remaining
            if set(dependencies.get(identifier, [])).issubset(resolved)
        )
        if not dependency_ready:
            waves.append({
                "wave": wave_number,
                "ready": [],
                "blocked": [],
                "staged": [],
                "waitingOnDependencies": sorted(remaining),
            })
            break
        ready = [identifier for identifier in dependency_ready if by_id[identifier].get("status") == "ACTIVE"]
        blocked = [identifier for identifier in dependency_ready if by_id[identifier].get("status") == "BLOCKED"]
        staged = [identifier for identifier in dependency_ready if by_id[identifier].get("status") == "STAGED"]
        waves.append({
            "wave": wave_number,
            "ready": ready,
            "blocked": blocked,
            "staged": staged,
            "waitingOnDependencies": [],
        })
        remaining -= set(dependency_ready)
        resolved.update(ready)
        wave_number += 1
    return waves


def _public_backlog_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if key != "evidenceMustExist"}


def _dependency_cycle(graph: dict[str, list[str]]) -> list[str]:
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(node: str) -> list[str]:
        if node in visiting:
            start = visiting.index(node)
            return visiting[start:] + [node]
        if node in visited:
            return []
        visiting.append(node)
        for dependency in graph.get(node, []):
            cycle = visit(dependency)
            if cycle:
                return cycle
        visiting.pop()
        visited.add(node)
        return []

    for identifier in graph:
        cycle = visit(identifier)
        if cycle:
            return cycle
    return []


def _load_configured_json(root: Path, value: Any, label: str, errors: list[str]) -> Any:
    target = _safe_path(root, value, label, errors)
    if target is None:
        return None
    if not target.is_file():
        errors.append(f"{label} does not exist: {value}")
        return None
    try:
        return read_json(target)
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"Unable to read {label}: {error}")
        return None


def _safe_path(root: Path, value: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{label} path must be a non-empty string")
        return None
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        errors.append(f"{label} path must remain repository-relative: {value}")
        return None
    try:
        return ensure_within(root, value)
    except ValueError as error:
        errors.append(f"{label}: {error}")
        return None


def _audit_source_binding(root: Path, source: Any, label: str, errors: list[str]) -> None:
    if not isinstance(source, dict):
        errors.append(f"{label}.source must be an object")
        return
    path = source.get("path")
    expected = source.get("sha256")
    target = _safe_path(root, path, f"{label}.source", errors)
    if target is None or not target.is_file():
        errors.append(f"{label}.source does not exist: {path}")
        return
    if not isinstance(expected, str) or len(expected) != 64:
        errors.append(f"{label}.source.sha256 must be a SHA-256 digest")
    elif sha256_file(target) != expected:
        errors.append(f"{label}.source hash mismatch: {path}")


def _audit_review_date(value: Any, max_age: Any, observed: date, label: str, errors: list[str]) -> None:
    try:
        reviewed = date.fromisoformat(value)
    except (TypeError, ValueError):
        errors.append(f"{label}.lastReviewed must be YYYY-MM-DD")
        return
    if not isinstance(max_age, int) or max_age < 1:
        errors.append("intent maxReviewAgeDays must be a positive integer")
    elif (observed - reviewed).days > max_age:
        errors.append(f"Stale intent record: {label} was reviewed {reviewed.isoformat()}")


def _audit_deadline(value: Any, observed: date, label: str, errors: list[str]) -> None:
    try:
        deadline = date.fromisoformat(value)
    except (TypeError, ValueError):
        errors.append(f"{label}.reviewAfter must be YYYY-MM-DD")
        return
    if observed > deadline:
        errors.append(f"{label} review expired on {deadline.isoformat()}")


def _audit_file(root: Path, value: Any, label: str, errors: list[str]) -> None:
    target = _safe_path(root, value, label, errors)
    if target and not target.is_file():
        errors.append(f"{label} does not exist: {value}")


def _string_list(value: Any, label: str, errors: list[str], *, required: bool = False) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        errors.append(f"{label} must be a string array")
        return []
    if required and not value:
        errors.append(f"{label} must not be empty")
    return value


def _check_refs(values: Iterable[str], valid: set[str], label: str, errors: list[str]) -> None:
    for value in values:
        if value not in valid:
            errors.append(f"Unknown {label}: {value}")


def _ids(records: list[dict[str, Any]]) -> set[str]:
    return {item["id"] for item in records if isinstance(item.get("id"), str)}


def _disabled(plane: str) -> dict[str, Any]:
    return {
        "status": "WARN",
        "enabled": False,
        "errors": [],
        "warnings": [f"{plane} plane is not configured; no readiness claim is available"],
    }
