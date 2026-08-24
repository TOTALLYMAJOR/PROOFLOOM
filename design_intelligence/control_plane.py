from __future__ import annotations

import fnmatch
import json
import re
import shutil
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any, Iterable

from .adoption import (
    audit_adoption_report,
    audit_design_system_health,
    evaluate_adoption,
)
from .architecture_graph import analyze_architecture_impact, build_architecture_graph
from .baselines import audit_baselines
from .memory import audit_memory
from .governance import audit_governance, governance_design_preflight
from .planes import (
    audit_backlog,
    audit_planes,
    intent_context_paths,
    route_task,
)
from .quality import audit_thresholds, load_thresholds, score_quality
from .repository import inspect_repository
from .storage import atomic_write_json, atomic_write_text, ensure_within, read_json, sha256_file


MANIFEST_NAME = "devctl.yaml"
API_VERSION = "devctl.design-intelligence/v2"
MANIFEST_KIND = "DevelopmentControlPlane"
TASK_STATES = ("active", "blocked", "completed")
TRUST_RANKS = {
    "policy": 1,
    "repository-governance": 2,
    "approved-task": 3,
    "domain-authority": 4,
    "institutional-memory": 5,
    "source-evidence": 6,
    "external-untrusted": 9,
}
DEFAULT_NEVER_AUTO_LOAD = [
    ".env*",
    "**/.env*",
    "**/*credential*",
    "**/*secret*",
    ".git/**",
    "node_modules/**",
]
DEFAULT_DESIGN_TRIGGERS = [
    "app/**",
    "components/**",
    "pages/**",
    "src/**",
    "styles/**",
    "tests/fixtures/visual-surface/**",
]
DEFAULT_JOURNEY_TRIGGERS = ["app/**", "components/**", "pages/**", "src/**"]
SCRIPT_CHECKS = (
    "lint",
    "typecheck",
    "test",
    "build",
    "precommit",
    "prepush",
    "check:boundaries",
    "check:contracts",
    "check:ci",
    "check:ui-skins",
    "verify:proof-boundaries",
    "release:readiness",
    "design:ci:quick",
    "design:ci:standard",
    "design:ci:full",
)


def load_manifest(repository_root: str | Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    path = root / MANIFEST_NAME
    if not path.is_file():
        raise ValueError(f"{MANIFEST_NAME} not found at {root}")
    payload = path.read_text(encoding="utf-8")
    try:
        manifest = json.loads(payload)
    except json.JSONDecodeError as json_error:
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as import_error:
            raise ValueError(
                f"{MANIFEST_NAME} must use JSON-compatible YAML when PyYAML is unavailable"
            ) from import_error
        try:
            manifest = yaml.safe_load(payload)
        except Exception as yaml_error:  # pragma: no cover - parser-specific details
            raise ValueError(f"Unable to parse {MANIFEST_NAME}: {json_error}") from yaml_error
    if not isinstance(manifest, dict):
        raise ValueError(f"{MANIFEST_NAME} must contain an object")
    return manifest


def manifest_schema() -> dict[str, Any]:
    source = files("design_intelligence").joinpath("data/schemas/devctl.schema.json")
    return json.loads(source.read_text(encoding="utf-8"))


def task_packet_schema() -> dict[str, Any]:
    source = files("design_intelligence").joinpath("data/schemas/task-packet.schema.json")
    return json.loads(source.read_text(encoding="utf-8"))


def architecture_graph_schema() -> dict[str, Any]:
    source = files("design_intelligence").joinpath("data/schemas/architecture-graph.schema.json")
    return json.loads(source.read_text(encoding="utf-8"))


def validate_control_plane(repository_root: str | Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    try:
        manifest = load_manifest(root)
    except ValueError as error:
        return {
            "status": "FAIL",
            "root": str(root),
            "manifest": MANIFEST_NAME,
            "schema": "devctl.schema.json",
            "errors": [str(error)],
            "warnings": [],
        }

    _validate_manifest_shape(manifest, errors)
    spec = manifest.get("spec") if isinstance(manifest.get("spec"), dict) else {}
    instructions = spec.get("instructions") if isinstance(spec.get("instructions"), dict) else {}
    instruction_root = instructions.get("root")
    if instruction_root:
        _validate_file_reference(root, instruction_root, "spec.instructions.root", errors)
    else:
        warnings.append("No root agent instruction file is declared")
    for index, adapter in enumerate(instructions.get("adapters", [])):
        _validate_file_reference(root, adapter, f"spec.instructions.adapters[{index}]", errors)

    authority_ids: set[str] = set()
    authority_paths: set[str] = set()
    for index, authority in enumerate(spec.get("authorities", [])):
        if not isinstance(authority, dict):
            continue
        identifier = authority.get("id")
        path = authority.get("path")
        trust = authority.get("trust")
        if identifier in authority_ids:
            errors.append(f"Duplicate authority id: {identifier}")
        if isinstance(identifier, str):
            authority_ids.add(identifier)
        if path in authority_paths:
            errors.append(f"Duplicate authority path: {path}")
        if isinstance(path, str):
            authority_paths.add(path)
            _validate_file_reference(root, path, f"spec.authorities[{index}].path", errors)
        if trust not in TRUST_RANKS:
            errors.append(f"spec.authorities[{index}].trust is invalid: {trust}")

    context = spec.get("context") if isinstance(spec.get("context"), dict) else {}
    max_files = context.get("maxFiles")
    max_bytes = context.get("maxBytes")
    if not isinstance(max_files, int) or not 1 <= max_files <= 50:
        errors.append("spec.context.maxFiles must be between 1 and 50")
    if not isinstance(max_bytes, int) or not 1024 <= max_bytes <= 1_000_000:
        errors.append("spec.context.maxBytes must be between 1024 and 1000000")

    tasks = spec.get("tasks") if isinstance(spec.get("tasks"), dict) else {}
    task_root = tasks.get("root")
    if isinstance(task_root, str):
        _validate_relative(task_root, "spec.tasks.root", errors)

    verification = spec.get("verification") if isinstance(spec.get("verification"), dict) else {}
    commands = verification.get("commands") if isinstance(verification.get("commands"), dict) else {}
    for check, command in commands.items():
        if not isinstance(check, str) or not check.strip():
            errors.append("Verification command ids must be non-empty strings")
        if not isinstance(command, list) or not command or not all(
            isinstance(part, str) and part for part in command
        ):
            errors.append(f"Verification command {check} must be a non-empty string array")
    for index, rule in enumerate(verification.get("rules", [])):
        if not isinstance(rule, dict):
            continue
        for check in rule.get("checks", []):
            if check not in commands:
                errors.append(f"spec.verification.rules[{index}] references unknown check: {check}")
        for path in rule.get("paths", []):
            _validate_relative(path, f"spec.verification.rules[{index}].paths", errors, allow_glob=True)

    design = spec.get("design") if isinstance(spec.get("design"), dict) else {}
    if design.get("enabled"):
        for key in ("memoryRoot", "qualityThresholds", "baselineManifest", "visualScenario"):
            value = design.get(key)
            if not isinstance(value, str):
                errors.append(f"spec.design.{key} is required when design integration is enabled")
                continue
            target = _safe_path(root, value, f"spec.design.{key}", errors)
            if target and not target.exists():
                errors.append(f"spec.design.{key} does not exist: {value}")
        adoption_report = design.get("adoptionReport")
        if adoption_report:
            _validate_file_reference(root, adoption_report, "spec.design.adoptionReport", errors)

    planes = spec.get("planes") if isinstance(spec.get("planes"), dict) else {}
    intent = planes.get("intent") if isinstance(planes.get("intent"), dict) else {}
    architecture = planes.get("architecture") if isinstance(planes.get("architecture"), dict) else {}
    intelligence = planes.get("intelligence") if isinstance(planes.get("intelligence"), dict) else {}
    if intent.get("enabled"):
        _validate_file_reference(root, intent.get("index"), "spec.planes.intent.index", errors)
    for index, pattern in enumerate(intent.get("journeyRequiredPaths", [])):
        _validate_relative(
            pattern,
            f"spec.planes.intent.journeyRequiredPaths[{index}]",
            errors,
            allow_glob=True,
        )
    backlog = intent.get("backlog") if isinstance(intent.get("backlog"), dict) else {}
    for index, source in enumerate(backlog.get("sources", [])):
        if not isinstance(source, dict):
            errors.append(f"spec.planes.intent.backlog.sources[{index}] must be an object")
            continue
        _validate_relative(
            source.get("path"),
            f"spec.planes.intent.backlog.sources[{index}].path",
            errors,
        )
    if architecture.get("enabled"):
        _validate_file_reference(
            root,
            architecture.get("standardsProfile"),
            "spec.planes.architecture.standardsProfile",
            errors,
        )
        for field in ("authorityPaths", "contractPaths"):
            for index, path in enumerate(architecture.get(field, [])):
                _validate_file_reference(
                    root, path, f"spec.planes.architecture.{field}[{index}]", errors
                )
        for index, pattern in enumerate(architecture.get("adrGlobs", [])):
            _validate_relative(
                pattern,
                f"spec.planes.architecture.adrGlobs[{index}]",
                errors,
                allow_glob=True,
            )
        for check in architecture.get("boundaryChecks", []):
            if check not in commands:
                errors.append(f"spec.planes.architecture.boundaryChecks references unknown check: {check}")
        technology = architecture.get("technologyCurrency", {})
        if isinstance(technology, dict):
            for field in ("manifests", "evidence"):
                for index, path in enumerate(technology.get(field, [])):
                    _validate_file_reference(
                        root,
                        path,
                        f"spec.planes.architecture.technologyCurrency.{field}[{index}]",
                        errors,
                    )
    _validate_impact_graph_config(root, architecture.get("impactGraph"), commands, errors)
    if intelligence.get("enabled"):
        _validate_file_reference(
            root,
            intelligence.get("routingPolicy"),
            "spec.planes.intelligence.routingPolicy",
            errors,
        )
    for field in ("instructionPaths", "rolePaths"):
        for index, path in enumerate(intelligence.get(field, [])):
            _validate_file_reference(root, path, f"spec.planes.intelligence.{field}[{index}]", errors)
    for index, path in enumerate(intelligence.get("skillRoots", [])):
        target = _safe_path(root, path, f"spec.planes.intelligence.skillRoots[{index}]", errors)
        if target and not target.is_dir():
            errors.append(f"spec.planes.intelligence.skillRoots[{index}] does not exist: {path}")

    return {
        "status": "PASS" if not errors else "FAIL",
        "root": str(root),
        "manifest": MANIFEST_NAME,
        "schema": "devctl.schema.json",
        "authorityCount": len(spec.get("authorities", [])),
        "verificationCommandCount": len(commands),
        "errors": errors,
        "warnings": warnings,
    }


def initialize_control_plane(
    repository_root: str | Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise ValueError(f"Repository root does not exist: {root}")
    discovery = discover_control_plane(root)
    if dry_run:
        return discovery
    manifest_path = root / MANIFEST_NAME
    if manifest_path.exists():
        report = validate_control_plane(root)
        return {
            "status": "ALREADY_CONFIGURED" if report["status"] == "PASS" else "FAIL",
            "root": str(root),
            "writes": [],
            "validation": report,
        }

    manifest = discovery["proposedManifest"]
    task_root = root / manifest["spec"]["tasks"]["root"]
    writes: list[str] = []
    atomic_write_json(manifest_path, manifest)
    writes.append(MANIFEST_NAME)
    version_path = root / ".dev/VERSION"
    atomic_write_text(version_path, "2\n")
    writes.append(".dev/VERSION")
    for state in TASK_STATES:
        keep = task_root / state / ".gitkeep"
        atomic_write_text(keep, "")
        writes.append(keep.relative_to(root).as_posix())
    validation = validate_control_plane(root)
    return {
        "status": "INITIALIZED" if validation["status"] == "PASS" else "REVIEW_REQUIRED",
        "root": str(root),
        "writes": writes,
        "preservedAuthorities": [item["path"] for item in manifest["spec"]["authorities"]],
        "readinessGaps": discovery["readinessGaps"],
        "validation": validation,
    }


def discover_control_plane(repository_root: str | Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise ValueError(f"Repository root does not exist: {root}")
    manifest = build_manifest(root)
    planes = manifest["spec"]["planes"]
    gaps: list[str] = []
    if not planes["intent"]["enabled"]:
        gaps.append("Intent index requires repository-owner review before intent readiness can pass")
    if not planes["architecture"]["enabled"]:
        gaps.append("Standards profile requires contextual applicability review before currency can pass")
    if not planes["intelligence"]["enabled"]:
        gaps.append("Capability routing policy requires authority review before intelligence routing can pass")
    if not manifest["spec"]["verification"]["commands"]:
        gaps.append("No repository-owned verification commands were discovered")
    return {
        "status": "REVIEW_REQUIRED" if gaps else "READY",
        "mode": "dry-run",
        "root": str(root),
        "writes": [],
        "proposedManifest": manifest,
        "discoveredAuthorities": manifest["spec"]["authorities"],
        "discoveredBacklogSources": planes["intent"]["backlog"]["sources"],
        "discoveredVerificationCommands": manifest["spec"]["verification"]["commands"],
        "readinessGaps": gaps,
        "claimBoundary": "Discovery proposes repository-relative bindings; it does not certify standards, approve intent, or mutate the repository.",
    }


def build_manifest(repository_root: str | Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    snapshot = inspect_repository(root)
    authorities = _discover_authorities(root)
    repository_triggers = _repository_trigger_paths(root)

    package = read_json(root / "package.json", {}) or {}
    scripts = package.get("scripts", {}) if isinstance(package, dict) else {}
    commands: dict[str, list[str]] = {}
    for script in SCRIPT_CHECKS:
        if script in scripts:
            commands[_verification_id(script)] = ["npm", "run", script]
    if (root / "pyproject.toml").is_file() and any((root / "tests").glob("test_*.py")):
        commands.setdefault(
            "unit-governance",
            ["python3", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
        )

    design_enabled = (root / ".design").is_dir()
    scenarios = sorted((root / "tests/design/scenarios").glob("*.json"))
    adoption_reports = sorted((root / "artifacts/design/adoptions").glob("*/adoption-report.json"))
    design: dict[str, Any] = {
        "enabled": design_enabled,
        "triggerPaths": repository_triggers,
    }
    if design_enabled:
        design.update({
            "memoryRoot": ".design/memory",
            "qualityThresholds": ".design/quality/thresholds.json",
            "baselineManifest": ".design/baselines/manifest.json",
            "visualScenario": _relative(root, scenarios[0]) if scenarios else "tests/design/scenarios/default.json",
        })
        if adoption_reports:
            design["adoptionReport"] = _relative(root, adoption_reports[-1])

    instruction_root = "AGENTS.md" if (root / "AGENTS.md").is_file() else None
    adapters = [
        relative
        for relative in ("adapters/codex/AGENTS.md", "adapters/claude/CLAUDE.md")
        if (root / relative).is_file()
    ]
    backlog_sources = _discover_backlog_sources(root)
    return {
        "apiVersion": API_VERSION,
        "kind": MANIFEST_KIND,
        "metadata": {
            "name": root.name,
            "owner": "repository",
            "phase": "0-5",
        },
        "spec": {
            "instructions": {"root": instruction_root, "adapters": adapters},
            "authorities": authorities,
            "context": {
                "maxFiles": 20,
                "maxBytes": 192000,
                "neverAutoLoad": DEFAULT_NEVER_AUTO_LOAD,
            },
            "tasks": {"root": ".dev/tasks"},
            "verification": {
                "commands": commands,
                "rules": _default_verification_rules(commands, repository_triggers),
            },
            "design": design,
            "planes": {
                "intent": {
                    "enabled": (root / ".dev/intent-index.json").is_file(),
                    "index": ".dev/intent-index.json",
                    "maxReviewAgeDays": 180,
                    "journeyRequiredPaths": repository_triggers,
                    "backlog": {
                        "completionPolicy": "all-terminal",
                        "sources": backlog_sources,
                        "terminalStatuses": [
                            "COMPLETED",
                            "CANCELLED",
                            "DEFERRED_WITH_AUTHORITY",
                        ],
                        "dependencies": {},
                    },
                },
                "architecture": {
                    "enabled": (root / ".dev/standards-profile.json").is_file(),
                    "standardsProfile": ".dev/standards-profile.json",
                    "maxReviewAgeDays": 90,
                    "authorityPaths": [
                        item["path"] for item in authorities if item["kind"] == "architecture"
                    ],
                    "contractPaths": [
                        path for path in ("package.json", "pyproject.toml") if (root / path).is_file()
                    ],
                    "adrGlobs": [
                        pattern for pattern in ("docs/architecture/ADR-*.md", "docs/architecture/adr/*.md")
                        if any(root.glob(pattern))
                    ],
                    "boundaryChecks": [
                        check for check in ("check-boundaries", "check-contracts", "unit-governance")
                        if check in commands
                    ],
                    "technologyCurrency": {
                        "policy": "contextual-not-latest",
                        "reviewedAt": datetime.now(timezone.utc).date().isoformat(),
                        "reviewAfter": datetime.now(timezone.utc).date().isoformat(),
                        "manifests": [
                            path for path in ("package.json", "package-lock.json", "pyproject.toml")
                            if (root / path).is_file()
                        ],
                        "evidence": [],
                    },
                    "impactGraph": {
                        "enabled": True,
                        "include": repository_triggers + [
                            "design_intelligence/**",
                            "scripts/**",
                            "tests/**",
                            "*.json",
                            "*.toml",
                            "*.yaml",
                        ],
                        "exclude": DEFAULT_NEVER_AUTO_LOAD + [
                            ".venv/**",
                            "artifacts/**",
                            "**/__pycache__/**",
                            "**/*.pyc",
                        ],
                        "maxSourceFiles": 2000,
                        "maxNodes": 5000,
                        "maxImpactNodes": 300,
                        "maxDepth": 4,
                        "codeowners": [".github/CODEOWNERS", "CODEOWNERS"],
                        "ownershipRules": [],
                        "securityRules": [],
                        "journeyBindings": [],
                    },
                },
                "intelligence": {
                    "enabled": (root / ".dev/model-routing.json").is_file(),
                    "routingPolicy": ".dev/model-routing.json",
                    "instructionPaths": [
                        path for path in ("AGENTS.md", "CLAUDE.md") if (root / path).is_file()
                    ],
                    "skillRoots": [path for path in ("skills", ".agents/skills") if (root / path).is_dir()],
                    "rolePaths": [],
                },
            },
            "discovery": {
                "repositoryMaturity": snapshot.repository_maturity.value,
                "frontend": snapshot.frontend,
                "existingDesignMemory": bool(snapshot.institutional_design_memory.authority_paths),
            },
        },
    }


def run_control_plane_doctor(repository_root: str | Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    validation = validate_control_plane(root)
    checks: list[dict[str, Any]] = [
        _check("manifest", validation["status"], validation["errors"]),
    ]
    if validation["status"] != "PASS":
        return {"status": "FAIL", "root": str(root), "checks": checks, "errors": validation["errors"]}

    manifest = load_manifest(root)
    spec = manifest["spec"]
    task_root = ensure_within(root, spec["tasks"]["root"])
    missing_states = [state for state in TASK_STATES if not (task_root / state).is_dir()]
    checks.append(_check(
        "task-store",
        "PASS" if not missing_states else "FAIL",
        [f"Missing task state directory: {state}" for state in missing_states],
    ))

    unavailable: list[str] = []
    for identifier, command in spec["verification"]["commands"].items():
        executable = command[0]
        if shutil.which(executable) is None:
            unavailable.append(f"{identifier}: executable not found: {executable}")
    checks.append(_check("verification-runtime", "PASS" if not unavailable else "FAIL", unavailable))

    design = spec.get("design", {})
    if design.get("enabled"):
        memory = audit_memory(root)
        checks.append(_check("design-memory", memory.get("status", "FAIL"), memory.get("errors", [])))
        baseline = audit_baselines(root)
        checks.append(_check("governed-baselines", baseline.get("status", "FAIL"), baseline.get("errors", [])))
        thresholds = load_thresholds(root / design["qualityThresholds"])
        threshold_errors = audit_thresholds(thresholds)
        checks.append(_check("quality-thresholds", "PASS" if not threshold_errors else "FAIL", threshold_errors))
        adoption_path = design.get("adoptionReport")
        if adoption_path:
            adoption = audit_adoption_report(root, adoption_path)
            checks.append(_check("design-adoption", adoption.get("status", "FAIL"), adoption.get("errors", [])))
        else:
            checks.append(_check("design-adoption", "WARN", ["No governed adoption report is configured"]))

    plane_audit = audit_planes(root, manifest)
    for identifier in ("intent", "architecture", "intelligence"):
        result = plane_audit[identifier]
        checks.append(_check(
            f"{identifier}-plane",
            result["status"],
            result.get("errors", []) + result.get("warnings", []),
        ))

    graph = build_architecture_graph(root, manifest)
    if graph.get("status") != "DISABLED":
        checks.append(_check(
            "architecture-impact-graph",
            graph.get("status", "FAIL"),
            graph.get("errors", []) + graph.get("warnings", []),
        ))

    failures = [check for check in checks if check["status"] == "FAIL"]
    warnings = [check for check in checks if check["status"] == "WARN"]
    status = "FAIL" if failures else "WARN" if warnings else "PASS"
    return {
        "status": status,
        "root": str(root),
        "checks": checks,
        "errors": [error for check in failures for error in check["details"]],
        "warnings": [warning for check in warnings for warning in check["details"]],
    }


def control_plane_health(repository_root: str | Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    validation = validate_control_plane(root)
    if validation["status"] != "PASS":
        return {"status": "FAIL", "root": str(root), "validation": validation, "errors": validation["errors"]}
    manifest = load_manifest(root)
    planes = audit_planes(root, manifest)
    architecture_graph = build_architecture_graph(root, manifest)
    intent = planes["intent"]
    backlog = intent.get("backlog", {})
    health_status = "FAIL" if architecture_graph.get("status") == "FAIL" else planes["status"]
    if health_status == "PASS" and backlog.get("completion") != "COMPLETE":
        health_status = "WARN"
    return {
        "status": health_status,
        "root": str(root),
        "planes": {
            "intent": intent["status"],
            "architecture": planes["architecture"]["status"],
            "intelligence": planes["intelligence"]["status"],
        },
        "journeys": intent.get("journeyCoverage", {}),
        "backlog": {
            "completion": backlog.get("completion", "UNKNOWN"),
            "items": backlog.get("itemCount", 0),
            "open": backlog.get("openCount", 0),
            "terminal": backlog.get("terminalCount", 0),
            "waves": backlog.get("waves", []),
        },
        "standards": {
            "catalogVersion": planes["architecture"].get("catalogVersion"),
            "reviewAfter": planes["architecture"].get("reviewAfter"),
            "certificationClaimed": False,
        },
        "architectureGraph": {
            "status": architecture_graph.get("status"),
            "nodes": architecture_graph.get("nodeCount", 0),
            "edges": architecture_graph.get("edgeCount", 0),
            "sha256": architecture_graph.get("graphSha256"),
            "truncated": architecture_graph.get("truncated", False),
        },
        "routing": {
            "vendorNeutral": planes["intelligence"].get("vendorNeutral", False),
            "capabilityClasses": planes["intelligence"].get("capabilityClassCount", 0),
        },
        "errors": (
            intent.get("errors", [])
            + planes["architecture"].get("errors", [])
            + planes["intelligence"].get("errors", [])
            + architecture_graph.get("errors", [])
        ),
        "warnings": (
            intent.get("warnings", [])
            + planes["architecture"].get("warnings", [])
            + planes["intelligence"].get("warnings", [])
            + architecture_graph.get("warnings", [])
        ),
    }


def create_task(repository_root: str | Path, packet: dict[str, Any]) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    manifest = load_manifest(root)
    errors = validate_task_packet(packet, manifest)
    _validate_task_intent_references(root, packet, manifest, errors)
    if errors:
        raise ValueError("Invalid task packet: " + "; ".join(errors))
    normalized = json.loads(json.dumps(packet))
    normalized.setdefault("createdAt", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    normalized["status"] = "ACTIVE"
    task_root = ensure_within(root, manifest["spec"]["tasks"]["root"])
    destination = task_root / "active" / f"{normalized['id']}.json"
    if destination.exists() or any((task_root / state / destination.name).exists() for state in TASK_STATES):
        raise ValueError(f"Task already exists: {normalized['id']}")
    atomic_write_json(destination, normalized)
    return {
        "status": "CREATED",
        "taskId": normalized["id"],
        "path": _relative(root, destination),
        "task": normalized,
    }


def validate_task_packet(packet: Any, manifest: dict[str, Any] | None = None) -> list[str]:
    if not isinstance(packet, dict):
        return ["task packet must be an object"]
    errors: list[str] = []
    required = (
        "schemaVersion", "id", "title", "status", "objective", "nonObjectives",
        "risk", "workType", "requiredCapabilities", "intent", "scope", "context",
        "verification", "completionCriteria",
    )
    errors.extend(f"task.{field} is required" for field in required if field not in packet)
    if packet.get("schemaVersion") != 2:
        errors.append("task.schemaVersion must be 2")
    identifier = packet.get("id")
    if not isinstance(identifier, str) or not identifier.startswith("TASK-") or not all(
        character.isupper() or character.isdigit() or character == "-" for character in identifier
    ):
        errors.append("task.id must match TASK-[A-Z0-9-]+")
    if packet.get("status") not in {
        "ACTIVE", "BLOCKED", "STAGED", "COMPLETED", "CANCELLED", "DEFERRED_WITH_AUTHORITY"
    }:
        errors.append("task.status is not a governed backlog status")
    if packet.get("risk") not in {"low", "medium", "high", "critical"}:
        errors.append("task.risk must be low, medium, high, or critical")
    for field in ("title", "objective"):
        if not isinstance(packet.get(field), str) or not packet.get(field, "").strip():
            errors.append(f"task.{field} must be a non-empty string")
    if not isinstance(packet.get("workType"), str) or not packet.get("workType", "").strip():
        errors.append("task.workType must be a non-empty string")
    _validate_string_array(packet.get("requiredCapabilities"), "task.requiredCapabilities", errors, required=True)
    intent = packet.get("intent")
    if not isinstance(intent, dict):
        errors.append("task.intent must be an object")
    else:
        for field in ("requirements", "journeys", "backlogItems", "successMetrics", "experiments"):
            _validate_string_array(intent.get(field), f"task.intent.{field}", errors)
    for field in ("nonObjectives", "completionCriteria"):
        value = packet.get(field)
        if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
            errors.append(f"task.{field} must be a string array")
    for container, field in (("scope", "paths"), ("context", "required"), ("context", "optional")):
        value = packet.get(container)
        paths = value.get(field) if isinstance(value, dict) else None
        if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
            errors.append(f"task.{container}.{field} must be a string array")
        else:
            for path in paths:
                _validate_relative(path, f"task.{container}.{field}", errors, allow_glob=container == "scope")
    verification = packet.get("verification")
    required_checks = verification.get("required") if isinstance(verification, dict) else None
    if not isinstance(required_checks, list) or not all(isinstance(item, str) and item for item in required_checks):
        errors.append("task.verification.required must be a string array")
    elif manifest:
        commands = manifest.get("spec", {}).get("verification", {}).get("commands", {})
        for check in required_checks:
            if check not in commands:
                errors.append(f"task.verification.required references unknown check: {check}")
    dependencies = packet.get("dependencies", [])
    _validate_string_array(dependencies, "task.dependencies", errors)
    terminal = packet.get("status") in {"CANCELLED", "DEFERRED_WITH_AUTHORITY"}
    if terminal:
        disposition = packet.get("terminalDisposition")
        if not isinstance(disposition, dict) or not all(
            isinstance(disposition.get(field), str) and disposition[field].strip()
            for field in ("authority", "rationale")
        ):
            errors.append("task.terminalDisposition requires authority and rationale")
    if manifest and isinstance(intent, dict):
        _validate_task_intent(packet, manifest, errors)
    return errors


def task_context(
    repository_root: str | Path,
    task_id: str,
    *,
    max_files: int | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    manifest = load_manifest(root)
    task, task_path = load_task(root, task_id, manifest)
    errors = validate_task_packet(task, manifest)
    _validate_task_intent_references(root, task, manifest, errors)
    if errors:
        return {"status": "FAIL", "taskId": task_id, "records": [], "errors": errors}

    context_policy = manifest["spec"]["context"]
    limit = max_files if max_files is not None else context_policy["maxFiles"]
    if not 1 <= limit <= context_policy["maxFiles"]:
        raise ValueError(f"max-files must be between 1 and {context_policy['maxFiles']}")
    byte_limit = context_policy["maxBytes"]
    denied = context_policy.get("neverAutoLoad", [])
    candidates: list[tuple[str, str, str]] = []
    for path in task["context"]["required"]:
        candidates.append((path, "required by approved task", "approved-task"))
    for path, reason in intent_context_paths(root, manifest, task):
        candidates.append((path, reason, "domain-authority"))
    for authority in sorted(
        manifest["spec"]["authorities"], key=lambda item: TRUST_RANKS[item["trust"]]
    ):
        candidates.append((authority["path"], f"declared {authority['kind']} authority", authority["trust"]))
    for path in task["context"]["optional"]:
        candidates.append((path, "optional task context", "domain-authority"))
    for pattern in task["scope"]["paths"]:
        for path in _expand_scope(root, pattern, limit * 2):
            candidates.append((path, f"matched task scope {pattern}", "source-evidence"))
    candidates = _coalesce_candidates(candidates)

    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    total_bytes = 0
    required_paths = set(task["context"]["required"])
    included_required: set[str] = set()
    for relative, reason, trust in candidates:
        if relative in seen:
            continue
        seen.add(relative)
        if _matches_any(relative, denied):
            if relative in required_paths:
                errors.append(f"Required context is blocked by neverAutoLoad: {relative}")
            continue
        try:
            target = ensure_within(root, relative)
        except ValueError as error:
            errors.append(str(error))
            continue
        if not target.is_file():
            if relative in required_paths:
                errors.append(f"Required context file does not exist: {relative}")
            continue
        size = target.stat().st_size
        if len(records) >= limit or total_bytes + size > byte_limit:
            if relative in required_paths:
                errors.append(f"Required context exceeds configured retrieval bounds: {relative}")
            continue
        record = {
            "path": relative,
            "reason": reason,
            "trust": trust,
            "trustRank": TRUST_RANKS[trust],
            "sha256": sha256_file(target),
            "bytes": size,
        }
        records.append(record)
        total_bytes += size
        if relative in required_paths:
            included_required.add(relative)
    missing_required = required_paths - included_required
    errors.extend(
        f"Required context was not retrieved: {path}"
        for path in sorted(missing_required)
        if not any(path in error for error in errors)
    )
    records.sort(key=lambda item: (item["trustRank"], item["path"]))
    return {
        "status": "PASS" if not errors else "FAIL",
        "taskId": task_id,
        "taskPath": _relative(root, task_path),
        "bounded": True,
        "limits": {"maxFiles": limit, "maxBytes": byte_limit},
        "selectedFiles": len(records),
        "selectedBytes": total_bytes,
        "records": records,
        "errors": errors,
    }


def analyze_impact(
    repository_root: str | Path,
    task_id: str,
    *,
    changed_paths: list[str] | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    manifest = load_manifest(root)
    task, task_path = load_task(root, task_id, manifest)
    task_errors = validate_task_packet(task, manifest)
    _validate_task_intent_references(root, task, manifest, task_errors)
    if task_errors:
        return {"status": "FAIL", "taskId": task_id, "checks": [], "errors": task_errors}
    selected_paths = list(changed_paths or task["scope"]["paths"])
    errors: list[str] = []
    for path in selected_paths:
        _validate_relative(path, "changed path", errors, allow_glob=True)
    if errors:
        return {"status": "FAIL", "taskId": task_id, "checks": [], "errors": errors}

    architecture_impact = analyze_architecture_impact(
        root,
        manifest,
        task,
        changed_paths=selected_paths,
    )
    verification = manifest["spec"]["verification"]
    reasons: dict[str, set[str]] = {}
    for check in task["verification"]["required"]:
        reasons.setdefault(check, set()).add("required by approved task packet")
    for check in architecture_impact.get("requiredChecks", []):
        reasons.setdefault(check, set()).add("required by impacted protected architecture boundary")
    affected_paths = sorted(set(selected_paths + architecture_impact.get("impactedPaths", [])))
    matched_rules: list[str] = []
    for index, rule in enumerate(verification["rules"]):
        matches = [
            path for path in affected_paths if _matches_any(path, rule["paths"])
        ]
        if not matches:
            continue
        rule_id = rule.get("id", f"rule-{index + 1}")
        matched_rules.append(rule_id)
        for check in rule["checks"]:
            reasons.setdefault(check, set()).add(
                f"{rule_id} matched {', '.join(sorted(matches))}"
            )

    commands = verification["commands"]
    checks = [
        {
            "id": check,
            "command": commands.get(check),
            "reasons": sorted(check_reasons),
            "available": check in commands,
        }
        for check, check_reasons in sorted(reasons.items())
    ]
    missing = [check["id"] for check in checks if not check["available"]]
    design = manifest["spec"].get("design", {})
    design_affected = bool(
        design.get("enabled")
        and any(_matches_any(path, design.get("triggerPaths", DEFAULT_DESIGN_TRIGGERS)) for path in selected_paths)
    )
    status = "FAIL" if missing or architecture_impact.get("status") != "PASS" else "PASS"
    route = route_task(root, manifest, task)
    if route["status"] == "FAIL":
        status = "FAIL"
    return {
        "status": status,
        "taskId": task_id,
        "taskPath": _relative(root, task_path),
        "changedPaths": selected_paths,
        "affectedPaths": affected_paths,
        "matchedRules": matched_rules,
        "designAffected": design_affected,
        "intent": task.get("intent", {}),
        "intelligenceRoute": route,
        "architectureImpact": architecture_impact,
        "checks": checks,
        "execution": {
            "performed": False,
            "reason": "The control plane produces a deterministic affected-verification plan; command execution remains an explicit CI or operator action.",
        },
        "errors": (
            [f"No command declared for required check: {check}" for check in missing]
            + architecture_impact.get("errors", [])
            + route.get("errors", [])
        ),
    }


def architecture_graph(repository_root: str | Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    manifest = load_manifest(root)
    return build_architecture_graph(root, manifest)


def architecture_impact(
    repository_root: str | Path,
    task_id: str,
    *,
    changed_paths: list[str] | None = None,
) -> dict[str, Any]:
    report = analyze_impact(repository_root, task_id, changed_paths=changed_paths)
    impact = report.get("architectureImpact")
    if not isinstance(impact, dict):
        return {
            "status": "FAIL",
            "taskId": task_id,
            "bounded": True,
            "errors": report.get("errors", ["Architecture impact is unavailable"]),
            "warnings": [],
        }
    return {
        **impact,
        "affectedPaths": report.get("affectedPaths", impact.get("impactedPaths", [])),
        "verificationChecks": report.get("checks", []),
        "matchedVerificationRules": report.get("matchedRules", []),
        "execution": report.get("execution", {"performed": False}),
    }


def route_task_by_id(repository_root: str | Path, task_id: str) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    manifest = load_manifest(root)
    task, task_path = load_task(root, task_id, manifest)
    errors = validate_task_packet(task, manifest)
    _validate_task_intent_references(root, task, manifest, errors)
    if errors:
        return {"status": "FAIL", "taskId": task_id, "errors": errors}
    return {**route_task(root, manifest, task), "taskPath": _relative(root, task_path)}


def inspect_design(repository_root: str | Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    snapshot = inspect_repository(root)
    governance = audit_governance(root)
    return {
        "status": "PASS" if governance["designGate"]["status"] == "READY" else "BLOCKED",
        "adapter": "design_intelligence.repository.inspect_repository",
        "duplicatedInfrastructure": False,
        "snapshot": snapshot.to_dict(),
        "designSystemHealth": audit_design_system_health(root),
        "governance": governance,
        "humanSummary": governance["humanSummary"],
    }


def evaluate_design_adoption(
    repository_root: str | Path,
    task: str,
    **kwargs: Any,
) -> dict[str, Any]:
    preflight = governance_design_preflight(repository_root)
    if preflight["status"] != "PASS":
        return {
            "status": "BLOCKED",
            "adapter": "design_intelligence.governance.governance_design_preflight",
            "duplicatedInfrastructure": False,
            "report": {
                "status": "BLOCKED",
                "implementationReady": False,
                "reason": "Repository understanding and governance must converge before design adoption.",
                "governancePreflight": preflight,
            },
        }
    report = evaluate_adoption(repository_root, task, **kwargs)
    return {
        "status": report["status"],
        "adapter": "design_intelligence.adoption.evaluate_adoption",
        "duplicatedInfrastructure": False,
        "report": report,
    }


def audit_design_adoption(
    repository_root: str | Path,
    report_path: str | Path,
) -> dict[str, Any]:
    audit = audit_adoption_report(repository_root, report_path)
    return {
        **audit,
        "adapter": "design_intelligence.adoption.audit_adoption_report",
        "duplicatedInfrastructure": False,
    }


def visual_plan(repository_root: str | Path, task_id: str) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    manifest = load_manifest(root)
    impact = analyze_impact(root, task_id)
    design = manifest["spec"].get("design", {})
    scenario = design.get("visualScenario")
    return {
        "status": impact["status"],
        "taskId": task_id,
        "adapter": "scripts/design/visual-qa.mjs",
        "scenario": scenario,
        "scenarioExists": bool(scenario and (root / scenario).is_file()),
        "qualityThresholds": design.get("qualityThresholds"),
        "baselineManifest": design.get("baselineManifest"),
        "impact": impact,
        "execution": {
            "performed": False,
            "boundary": "The facade selects governed visual evidence; the existing Playwright hierarchy performs rendering.",
        },
    }


def audit_visual_evidence(
    repository_root: str | Path,
    qa_report_path: str | Path,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    manifest = load_manifest(root)
    design = manifest["spec"].get("design", {})
    if not design.get("enabled"):
        return {"status": "FAIL", "errors": ["Design integration is disabled"]}
    qa_path = ensure_within(root, qa_report_path)
    qa_report = read_json(qa_path, {}) or {}
    thresholds = load_thresholds(root / design["qualityThresholds"])
    threshold_errors = audit_thresholds(thresholds)
    quality = score_quality(qa_report, thresholds).to_dict() if not threshold_errors else None
    baselines = audit_baselines(root)
    errors = list(threshold_errors)
    if quality and quality["status"] != "PASS":
        errors.append("Deterministic quality score did not pass")
    if baselines.get("status") != "PASS":
        errors.extend(baselines.get("errors", ["Governed baseline audit did not pass"]))
    return {
        "status": "PASS" if not errors else "FAIL",
        "adapter": "design_intelligence.quality.score_quality + design_intelligence.baselines.audit_baselines",
        "duplicatedInfrastructure": False,
        "qaReport": _relative(root, qa_path),
        "qaReportSha256": sha256_file(qa_path),
        "quality": quality,
        "baselines": baselines,
        "errors": errors,
    }


def load_task(
    repository_root: str | Path,
    task_id: str,
    manifest: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Path]:
    root = Path(repository_root).resolve()
    configured = manifest or load_manifest(root)
    task_root = ensure_within(root, configured["spec"]["tasks"]["root"])
    matches = [task_root / state / f"{task_id}.json" for state in TASK_STATES]
    existing = [path for path in matches if path.is_file()]
    if not existing:
        raise ValueError(f"Task not found: {task_id}")
    if len(existing) > 1:
        raise ValueError(f"Task exists in multiple states: {task_id}")
    task = read_json(existing[0], {}) or {}
    if not isinstance(task, dict):
        raise ValueError(f"Task packet must contain an object: {task_id}")
    return task, existing[0]


def _validate_manifest_shape(manifest: dict[str, Any], errors: list[str]) -> None:
    if manifest.get("apiVersion") != API_VERSION:
        errors.append(f"apiVersion must be {API_VERSION}")
    if manifest.get("kind") != MANIFEST_KIND:
        errors.append(f"kind must be {MANIFEST_KIND}")
    metadata = manifest.get("metadata")
    if not isinstance(metadata, dict) or not isinstance(metadata.get("name"), str) or not metadata.get("name"):
        errors.append("metadata.name is required")
    elif metadata.get("owner") != "repository" or metadata.get("phase") != "0-5":
        errors.append("metadata must declare repository ownership and phase 0-5")
    spec = manifest.get("spec")
    if not isinstance(spec, dict):
        errors.append("spec must be an object")
        return
    for field in ("instructions", "authorities", "context", "tasks", "verification", "design", "planes"):
        if field not in spec:
            errors.append(f"spec.{field} is required")
    if not isinstance(spec.get("authorities"), list):
        errors.append("spec.authorities must be an array")
    else:
        for index, authority in enumerate(spec["authorities"]):
            if not isinstance(authority, dict):
                errors.append(f"spec.authorities[{index}] must be an object")
                continue
            for field in ("id", "path", "trust", "kind"):
                if not isinstance(authority.get(field), str) or not authority[field]:
                    errors.append(f"spec.authorities[{index}].{field} is required")
    verification = spec.get("verification")
    if not isinstance(verification, dict):
        errors.append("spec.verification must be an object")
    elif not isinstance(verification.get("rules"), list):
        errors.append("spec.verification.rules must be an array")
    else:
        for index, rule in enumerate(verification["rules"]):
            if not isinstance(rule, dict):
                errors.append(f"spec.verification.rules[{index}] must be an object")
                continue
            for field in ("paths", "checks"):
                if not isinstance(rule.get(field), list) or not rule[field]:
                    errors.append(f"spec.verification.rules[{index}].{field} must be a non-empty array")
    planes = spec.get("planes")
    if not isinstance(planes, dict):
        errors.append("spec.planes must be an object")
    else:
        for plane in ("intent", "architecture", "intelligence"):
            if not isinstance(planes.get(plane), dict):
                errors.append(f"spec.planes.{plane} must be an object")
        intent = planes.get("intent", {})
        if isinstance(intent, dict):
            if not isinstance(intent.get("enabled"), bool):
                errors.append("spec.planes.intent.enabled must be boolean")
            if not isinstance(intent.get("maxReviewAgeDays"), int) or intent.get("maxReviewAgeDays", 0) < 1:
                errors.append("spec.planes.intent.maxReviewAgeDays must be positive")
            if not isinstance(intent.get("journeyRequiredPaths"), list):
                errors.append("spec.planes.intent.journeyRequiredPaths must be an array")
            backlog = intent.get("backlog")
            if not isinstance(backlog, dict):
                errors.append("spec.planes.intent.backlog must be an object")
            else:
                if backlog.get("completionPolicy") != "all-terminal":
                    errors.append("spec.planes.intent.backlog.completionPolicy must be all-terminal")
                terminal_statuses = backlog.get("terminalStatuses")
                if not isinstance(terminal_statuses, list) or not all(
                    isinstance(item, str) for item in terminal_statuses
                ) or set(terminal_statuses) != {"COMPLETED", "CANCELLED", "DEFERRED_WITH_AUTHORITY"}:
                    errors.append("spec.planes.intent.backlog.terminalStatuses is invalid")
                if not isinstance(backlog.get("sources"), list) or not backlog["sources"]:
                    errors.append("spec.planes.intent.backlog.sources must be a non-empty array")
                if not isinstance(backlog.get("dependencies"), dict):
                    errors.append("spec.planes.intent.backlog.dependencies must be an object")
        architecture = planes.get("architecture", {})
        if isinstance(architecture, dict):
            if not isinstance(architecture.get("enabled"), bool):
                errors.append("spec.planes.architecture.enabled must be boolean")
            if not isinstance(architecture.get("maxReviewAgeDays"), int) or architecture.get("maxReviewAgeDays", 0) < 1:
                errors.append("spec.planes.architecture.maxReviewAgeDays must be positive")
            for field in ("authorityPaths", "contractPaths", "adrGlobs", "boundaryChecks"):
                if not isinstance(architecture.get(field), list):
                    errors.append(f"spec.planes.architecture.{field} must be an array")
                elif architecture.get("enabled") and not architecture[field]:
                    errors.append(f"spec.planes.architecture.{field} must not be empty when enabled")
            if not isinstance(architecture.get("technologyCurrency"), dict):
                errors.append("spec.planes.architecture.technologyCurrency must be an object")
            if not isinstance(architecture.get("impactGraph"), dict):
                errors.append("spec.planes.architecture.impactGraph must be an object")
        intelligence = planes.get("intelligence", {})
        if isinstance(intelligence, dict):
            if not isinstance(intelligence.get("enabled"), bool):
                errors.append("spec.planes.intelligence.enabled must be boolean")
            for field in ("instructionPaths", "skillRoots", "rolePaths"):
                if not isinstance(intelligence.get(field), list):
                    errors.append(f"spec.planes.intelligence.{field} must be an array")


def _validate_impact_graph_config(
    root: Path,
    value: Any,
    commands: dict[str, list[str]],
    errors: list[str],
) -> None:
    label = "spec.planes.architecture.impactGraph"
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return
    if not isinstance(value.get("enabled"), bool):
        errors.append(f"{label}.enabled must be boolean")
    for field in ("include", "exclude"):
        patterns = value.get(field)
        if not isinstance(patterns, list) or not all(
            isinstance(item, str) and item for item in patterns
        ):
            errors.append(f"{label}.{field} must be a string array")
            continue
        if field == "include" and value.get("enabled") and not patterns:
            errors.append(f"{label}.include must not be empty when enabled")
        for index, pattern in enumerate(patterns):
            _validate_relative(pattern, f"{label}.{field}[{index}]", errors, allow_glob=True)
    limits = {
        "maxSourceFiles": (1, 10000),
        "maxNodes": (1, 25000),
        "maxImpactNodes": (1, 2000),
        "maxDepth": (1, 8),
    }
    for field, (minimum, maximum) in limits.items():
        candidate = value.get(field)
        if not isinstance(candidate, int) or not minimum <= candidate <= maximum:
            errors.append(f"{label}.{field} must be between {minimum} and {maximum}")
    for index, path in enumerate(value.get("codeowners", [])):
        _validate_relative(path, f"{label}.codeowners[{index}]", errors)

    identifiers: set[str] = set()
    for field in ("ownershipRules", "securityRules"):
        rules = value.get(field)
        if not isinstance(rules, list):
            errors.append(f"{label}.{field} must be an array")
            continue
        for index, rule in enumerate(rules):
            rule_label = f"{label}.{field}[{index}]"
            if not isinstance(rule, dict):
                errors.append(f"{rule_label} must be an object")
                continue
            identifier = rule.get("id")
            if not isinstance(identifier, str) or not identifier:
                errors.append(f"{rule_label}.id is required")
            elif identifier in identifiers:
                errors.append(f"Duplicate architecture graph rule id: {identifier}")
            else:
                identifiers.add(identifier)
            paths = rule.get("paths")
            if not isinstance(paths, list) or not paths:
                errors.append(f"{rule_label}.paths must be a non-empty array")
            else:
                for path_index, pattern in enumerate(paths):
                    _validate_relative(
                        pattern,
                        f"{rule_label}.paths[{path_index}]",
                        errors,
                        allow_glob=True,
                    )
            if field == "ownershipRules":
                owners = rule.get("owners")
                if not isinstance(owners, list) or not owners or not all(
                    isinstance(owner, str) and owner for owner in owners
                ):
                    errors.append(f"{rule_label}.owners must be a non-empty string array")
            else:
                checks = rule.get("checks", [])
                if not isinstance(checks, list) or not all(
                    isinstance(check, str) and check for check in checks
                ):
                    errors.append(f"{rule_label}.checks must be a string array")
                else:
                    for check in checks:
                        if check not in commands:
                            errors.append(f"{rule_label} references unknown check: {check}")

    bindings = value.get("journeyBindings")
    if not isinstance(bindings, list):
        errors.append(f"{label}.journeyBindings must be an array")
        return
    for index, binding in enumerate(bindings):
        binding_label = f"{label}.journeyBindings[{index}]"
        if not isinstance(binding, dict):
            errors.append(f"{binding_label} must be an object")
            continue
        if not isinstance(binding.get("journeyId"), str) or not binding["journeyId"]:
            errors.append(f"{binding_label}.journeyId is required")
        paths = binding.get("paths")
        if not isinstance(paths, list) or not paths:
            errors.append(f"{binding_label}.paths must be a non-empty array")
            continue
        for path_index, pattern in enumerate(paths):
            _validate_relative(
                pattern,
                f"{binding_label}.paths[{path_index}]",
                errors,
                allow_glob=True,
            )


def _validate_file_reference(root: Path, value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value:
        errors.append(f"{label} must be a non-empty string")
        return
    target = _safe_path(root, value, label, errors)
    if target and not target.is_file():
        errors.append(f"{label} does not exist: {value}")


def _safe_path(root: Path, value: str, label: str, errors: list[str]) -> Path | None:
    _validate_relative(value, label, errors)
    if errors and any(error.startswith(label) for error in errors):
        return None
    try:
        return ensure_within(root, value)
    except ValueError as error:
        errors.append(f"{label}: {error}")
        return None


def _validate_relative(value: Any, label: str, errors: list[str], *, allow_glob: bool = False) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a non-empty relative path")
        return
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        errors.append(f"{label} must remain repository-relative: {value}")
    if not allow_glob and any(character in value for character in "*?["):
        errors.append(f"{label} cannot contain glob syntax: {value}")


def _default_verification_rules(
    commands: dict[str, list[str]],
    repository_triggers: list[str] | None = None,
) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    unit_check = "unit-governance" if "unit-governance" in commands else None
    design_check = "design-standard" if "design-standard" in commands else "design-quick" if "design-quick" in commands else None
    if unit_check:
        rules.append({
            "id": "python-control-plane",
            "paths": ["design_intelligence/**", "tests/**", "scripts/**", "devctl.yaml", ".dev/**"],
            "checks": [unit_check],
        })
    if design_check:
        rules.append({
            "id": "rendered-design-surface",
            "paths": repository_triggers or DEFAULT_DESIGN_TRIGGERS,
            "checks": [design_check],
        })
    return rules


def _discover_authorities(root: Path) -> list[dict[str, str]]:
    governance = audit_governance(root)
    equivalent_bindings = {
        path for system in governance["equivalentSystems"] for path in system["bindings"]
    }
    registered_bindings = _registered_governing_paths(root)
    explicit_bindings = {
        "AGENTS.md",
        "CLAUDE.md",
        "docs/backlog-now.md",
        "docs/backlog-next.md",
        "docs/architecture/mvp-golden-path.md",
        "docs/architecture/solution-design.md",
        "docs/product/platform-specification.md",
    }
    candidates: dict[str, dict[str, Any]] = {}
    for record in governance["authorities"]:
        roles = set(record["roles"])
        if record["lifecycle"] in {"historical", "evidence"}:
            continue
        include = (
            record["path"] in equivalent_bindings
            or record["path"] in registered_bindings
            or record["path"] in explicit_bindings
            or ("adrs" in roles and record["lifecycle"] == "active")
            or record["path"] == "docs/governance/README.md"
            or Path(record["path"]).name in {"ARCHITECTURE.md", "solution.md"}
        )
        if include:
            candidates[record["path"]] = record
    authorities: list[dict[str, str]] = []
    for relative, record in sorted(candidates.items()):
        roles = set(record["roles"])
        if "instructions" in roles or "governance" in roles:
            trust, kind = "repository-governance", "instructions" if "instructions" in roles else "governance"
        elif "backlog" in roles:
            trust, kind = "approved-task", "backlog"
        elif roles & {"architecture", "adrs"}:
            trust, kind = "domain-authority", "architecture"
        elif "design" in roles:
            trust, kind = "domain-authority", "design"
        elif roles & {"vision", "requirements", "personas", "journeys", "metrics"}:
            trust, kind = "domain-authority", "product"
        elif "security" in roles:
            trust, kind = "domain-authority", "security"
        elif "contracts" in roles:
            trust, kind = "domain-authority", "contracts"
        else:
            trust, kind = "domain-authority", "documentation"
        authorities.append({
            "id": _authority_id(relative),
            "path": relative,
            "trust": trust,
            "kind": kind,
        })
    return authorities


def _registered_governing_paths(root: Path) -> set[str]:
    manifest = root / "docs/atlas/atlas-manifest.yaml"
    if not manifest.is_file():
        return set()
    text = manifest.read_text(encoding="utf-8", errors="ignore")
    section = text.split("included_domains:", 1)[0]
    return {
        match.group(1)
        for match in re.finditer(
            r"(?:^\s+path:\s*|^\s+-\s+)([A-Za-z0-9_.@/-]+\.(?:md|mdx|json|yaml|yml))\s*$",
            section,
            re.MULTILINE,
        )
        if (root / match.group(1)).is_file()
    }


def _discover_backlog_sources(root: Path) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    candidates = (
        ("docs/backlog-now.md", "active", True),
        ("docs/backlog-next.md", "staged", True),
        ("docs/backlog.md", "historical", False),
    )
    for relative, role, include in candidates:
        if (root / relative).is_file():
            sources.append({
                "path": relative,
                "role": role,
                "parser": "markdown-headings",
                "includeInCompletion": include,
                "requireItems": True,
            })
    task_root = root / ".dev/tasks"
    has_task_packets = task_root.is_dir() and any(task_root.glob("*/*.json"))
    if has_task_packets or not sources:
        sources.insert(0, {
            "path": ".dev/tasks",
            "role": "active",
            "parser": "task-store",
            "includeInCompletion": True,
            "requireItems": False,
        })
    return sources


def _repository_trigger_paths(root: Path) -> list[str]:
    triggers = set(DEFAULT_DESIGN_TRIGGERS)
    package = read_json(root / "package.json", {}) or {}
    workspaces = package.get("workspaces", []) if isinstance(package, dict) else []
    if isinstance(workspaces, dict):
        workspaces = workspaces.get("packages", [])
    for pattern in workspaces if isinstance(workspaces, list) else []:
        if not isinstance(pattern, str):
            continue
        base = pattern.split("*")[0].rstrip("/")
        if base and (root / base).is_dir():
            triggers.add(f"{base}/**")
    for base in ("apps", "packages", "libs"):
        if (root / base).is_dir():
            triggers.add(f"{base}/**")
    return sorted(triggers)


def _authority_id(relative: str) -> str:
    value = re_sub_non_alnum(relative.removesuffix(".md").lower())
    return value or "repository-authority"


def _verification_id(script: str) -> str:
    design_aliases = {
        "design:ci:quick": "design-quick",
        "design:ci:standard": "design-standard",
        "design:ci:full": "design-full",
    }
    return design_aliases.get(script, re_sub_non_alnum(script.lower()))


def re_sub_non_alnum(value: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def _validate_string_array(
    value: Any,
    label: str,
    errors: list[str],
    *,
    required: bool = False,
) -> None:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        errors.append(f"{label} must be a string array")
    elif required and not value:
        errors.append(f"{label} must not be empty")


def _validate_task_intent(packet: dict[str, Any], manifest: dict[str, Any], errors: list[str]) -> None:
    planes = manifest.get("spec", {}).get("planes", {})
    config = planes.get("intent", {})
    if not config.get("enabled"):
        return
    # The index contents are validated again during task creation with the repository root.
    # Shape-level checks here still enforce user-facing journey binding.
    intent = packet.get("intent", {})
    triggers = config.get("journeyRequiredPaths", DEFAULT_JOURNEY_TRIGGERS)
    user_facing = any(
        _matches_any(path, triggers)
        for path in packet.get("scope", {}).get("paths", [])
    ) or packet.get("workType") in {"frontend", "product", "ux", "design"}
    if user_facing:
        for field in ("requirements", "journeys", "successMetrics"):
            if not intent.get(field):
                errors.append(f"User-facing task requires task.intent.{field}")
    if packet.get("id") not in intent.get("backlogItems", []):
        errors.append("task.intent.backlogItems must include the task id")


def _validate_task_intent_references(
    root: Path,
    packet: dict[str, Any],
    manifest: dict[str, Any],
    errors: list[str],
) -> None:
    config = manifest.get("spec", {}).get("planes", {}).get("intent", {})
    if not config.get("enabled"):
        return
    index = read_json(ensure_within(root, config["index"]), {}) or {}
    task_intent = packet.get("intent", {})
    for field in ("requirements", "journeys", "successMetrics", "experiments"):
        valid = {
            item.get("id") for item in index.get(field, []) if isinstance(item, dict)
        }
        for identifier in task_intent.get(field, []):
            if identifier not in valid:
                errors.append(f"task.intent.{field} references unknown id: {identifier}")
    backlog = audit_backlog(root, config.get("backlog", {}))
    backlog_ids = {item.get("id") for item in backlog.get("items", [])}
    for identifier in task_intent.get("backlogItems", []):
        if identifier not in backlog_ids and identifier != packet.get("id"):
            errors.append(f"task.intent.backlogItems references unknown id: {identifier}")


def _expand_scope(root: Path, pattern: str, limit: int) -> list[str]:
    if not any(character in pattern for character in "*?["):
        target = ensure_within(root, pattern)
        if target.is_file():
            return [pattern]
        if target.is_dir():
            return [
                _relative(root, path)
                for path in sorted(target.rglob("*"))
                if path.is_file() and not _ignored_path(root, path)
            ][:limit]
        return []
    return [
        _relative(root, path)
        for path in sorted(root.glob(pattern))
        if path.is_file() and not _ignored_path(root, path)
    ][:limit]


def _ignored_path(root: Path, path: Path) -> bool:
    relative = path.relative_to(root)
    return any(part in {".git", "node_modules", ".venv", "__pycache__"} for part in relative.parts)


def _coalesce_candidates(candidates: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    ordered: list[str] = []
    selected: dict[str, tuple[str, str]] = {}
    reasons: dict[str, list[str]] = {}
    for path, reason, trust in candidates:
        if path not in selected:
            ordered.append(path)
            selected[path] = (reason, trust)
            reasons[path] = [reason]
            continue
        reasons[path].append(reason)
        if TRUST_RANKS[trust] < TRUST_RANKS[selected[path][1]]:
            selected[path] = (reason, trust)
    return [
        (path, "; ".join(dict.fromkeys(reasons[path])), selected[path][1])
        for path in ordered
    ]


def _matches_any(path: str, patterns: Iterable[str]) -> bool:
    normalized = path.replace("\\", "/")
    for pattern in patterns:
        normalized_pattern = pattern.replace("\\", "/")
        if fnmatch.fnmatchcase(normalized, normalized_pattern):
            return True
        if normalized_pattern.endswith("/**") and normalized.startswith(normalized_pattern[:-3].rstrip("/") + "/"):
            return True
        if normalized_pattern == normalized:
            return True
    return False


def _check(identifier: str, status: str, details: list[str]) -> dict[str, Any]:
    return {"id": identifier, "status": status, "details": details}


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root).as_posix()
