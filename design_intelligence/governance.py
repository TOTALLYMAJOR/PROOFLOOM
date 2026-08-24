from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .storage import atomic_write_json, atomic_write_text, read_json


SCHEMA_VERSION = 1
GENERATOR = "design-intelligence-governance"
GOVERNANCE_ROOT = ".dev/governance"
MAP_PATH = f"{GOVERNANCE_ROOT}/governance-map.json"
ADAPTER_PATH = f"{GOVERNANCE_ROOT}/repository-adapter.json"
MANIFEST_PATH = f"{GOVERNANCE_ROOT}/convergence-manifest.json"
READOUT_PATH = f"{GOVERNANCE_ROOT}/HUMAN-READOUT.md"
PLAN_PATH = f"{GOVERNANCE_ROOT}/rehabilitation-plan.json"
RATIFICATION_PATH = f"{GOVERNANCE_ROOT}/OWNER-RATIFICATION.md"

IGNORED_DIRECTORIES = {
    ".git",
    ".next",
    ".turbo",
    ".venv",
    ".vercel",
    "artifacts",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "output",
    "vendor",
    "__pycache__",
}

TEXT_SUFFIXES = {".json", ".md", ".mdx", ".toml", ".txt", ".yaml", ".yml"}
CRITICAL_ROLES = {
    "instructions",
    "skills",
    "governance",
    "vision",
    "principles",
    "personas",
    "requirements",
    "journeys",
    "backlog",
    "architecture",
    "adrs",
    "contracts",
    "security",
    "design",
    "delivery",
}
CORE_UNDERSTANDING_ROLES = {
    "instructions",
    "vision",
    "requirements",
    "journeys",
    "architecture",
    "backlog",
}
BLOCKING_SEVERITIES = {"P0", "P1"}


def audit_governance(repository_root: str | Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise ValueError(f"Repository root does not exist: {root}")

    tracked, tracking_mode = _tracked_files(root)
    records = _authority_records(root, tracked)
    by_role = _group_records(records)
    equivalents = _detect_equivalent_systems(root, records)
    journeys = _extract_journeys(root, by_role.get("journeys", []))
    backlog = _backlog_summary(
        root,
        [item for item in records if "backlog" in item["roles"]],
        journeys,
    )
    script_damage = _audit_package_scripts(root, tracked)
    untracked = _untracked_authority_candidates(root)
    findings = _build_findings(
        root,
        records,
        by_role,
        equivalents,
        journeys,
        backlog,
        script_damage,
        untracked,
    )
    drift = _audit_authority_drift(root, records)
    findings.extend(drift["findings"])
    findings = sorted(findings, key=_finding_sort_key)
    counts = _finding_counts(findings)
    finalization = _finalization_readiness(by_role, journeys, equivalents, findings)
    design_gate = {
        "status": "LOCKED" if any(item["severity"] in BLOCKING_SEVERITIES for item in findings) else "READY",
        "reason": _design_gate_reason(findings, finalization),
        "requiredBeforeDesign": [
            item["id"] for item in findings if item["severity"] in BLOCKING_SEVERITIES
        ],
    }
    implementation_roots = _implementation_roots(root)

    report: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedBy": GENERATOR,
        "status": "REVIEW_REQUIRED" if design_gate["status"] == "LOCKED" else "READY",
        "observedAt": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "trackingMode": tracking_mode,
        "authoritySummary": {
            role: len(items) for role, items in sorted(by_role.items())
        },
        "authorities": records,
        "equivalentSystems": equivalents,
        "implementationRoots": implementation_roots,
        "journeyModel": journeys,
        "backlogModel": backlog,
        "scriptDamage": script_damage,
        "untrackedAuthorityCandidates": untracked,
        "authorityDrift": drift,
        "findings": findings,
        "findingCounts": counts,
        "finalizationReadiness": finalization,
        "designGate": design_gate,
        "claimBoundary": (
            "The audit reconstructs repository governance from tracked evidence. "
            "It does not ratify product vision, resolve human decisions, or claim implementation completion."
        ),
    }
    report["humanSummary"] = render_governance_readout(report)
    report["reportSha256"] = _digest(_stable_report(report))
    return report


def plan_governance_convergence(repository_root: str | Path) -> dict[str, Any]:
    audit = audit_governance(repository_root)
    actions: list[dict[str, Any]] = []

    for system in audit["equivalentSystems"]:
        actions.append({
            "id": f"BIND-{system['id'].upper()}",
            "action": "PRESERVE_AND_BIND",
            "target": system["id"],
            "reason": "Use the established repository system instead of installing a competing authority.",
            "automatic": True,
            "mutatesCanonicalAuthority": False,
        })

    actions.extend([
        {
            "id": "WRITE-GOVERNANCE-MAP",
            "action": "WRITE_DERIVED_INDEX",
            "target": MAP_PATH,
            "reason": "Make current authority, scope, lifecycle, conflicts, and journeys retrievable.",
            "automatic": True,
            "mutatesCanonicalAuthority": False,
        },
        {
            "id": "WRITE-REPOSITORY-ADAPTER",
            "action": "WRITE_DERIVED_ADAPTER",
            "target": ADAPTER_PATH,
            "reason": "Bind existing repository structures to the control plane without moving runtime code.",
            "automatic": True,
            "mutatesCanonicalAuthority": False,
        },
        {
            "id": "WRITE-CONVERGENCE-MANIFEST",
            "action": "BASELINE_CRITICAL_AUTHORITY",
            "target": MANIFEST_PATH,
            "reason": "Detect later unreviewed changes to vision, instructions, journeys, architecture, and policy.",
            "automatic": True,
            "mutatesCanonicalAuthority": False,
        },
        {
            "id": "WRITE-HUMAN-READOUT",
            "action": "WRITE_HUMAN_REPORT",
            "target": READOUT_PATH,
            "reason": "Explain the product journey, governing structure, blockers, and next actions in product language.",
            "automatic": True,
            "mutatesCanonicalAuthority": False,
        },
        {
            "id": "WRITE-REHABILITATION-PLAN",
            "action": "WRITE_EXECUTION_PLAN",
            "target": PLAN_PATH,
            "reason": "Turn detected gaps into explicit automatic and authority-bound completion work.",
            "automatic": True,
            "mutatesCanonicalAuthority": False,
        },
        {
            "id": "WRITE-OWNER-RATIFICATION",
            "action": "WRITE_RATIFICATION_PACKET",
            "target": RATIFICATION_PATH,
            "reason": "Present vision, authority, architecture, and exception decisions that require an owner.",
            "automatic": True,
            "mutatesCanonicalAuthority": False,
        },
    ])

    for finding in audit["findings"]:
        if finding["severity"] not in BLOCKING_SEVERITIES:
            continue
        actions.append({
            "id": f"RESOLVE-{finding['id']}",
            "action": finding["requiredAction"],
            "target": finding.get("paths", []),
            "reason": finding["message"],
            "automatic": False,
            "mutatesCanonicalAuthority": finding["category"] in {
                "authority-conflict", "vision", "journey", "governance-conflict"
            },
            "authority": finding.get("authority", "repository-owner"),
        })

    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedBy": GENERATOR,
        "status": audit["status"],
        "root": audit["root"],
        "auditSha256": audit["reportSha256"],
        "automaticActions": [item for item in actions if item["automatic"]],
        "authorityBoundActions": [item for item in actions if not item["automatic"]],
        "designGate": audit["designGate"],
        "finalizationReadiness": audit["finalizationReadiness"],
        "actions": actions,
        "audit": audit,
    }


def apply_governance_convergence(
    repository_root: str | Path,
    *,
    ratification_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    plan = plan_governance_convergence(root)
    audit = plan["audit"]
    ratification = _validate_authority_drift_ratification(root, audit, ratification_path)
    adapter = _build_repository_adapter(root, audit)
    manifest = _build_convergence_manifest(root, audit, ratification)
    writes = {
        MAP_PATH: _map_payload(audit),
        ADAPTER_PATH: adapter,
        MANIFEST_PATH: manifest,
        PLAN_PATH: _rehabilitation_payload(plan),
    }
    changed: list[str] = []
    preserved: list[str] = []
    for relative, payload in writes.items():
        target = root / relative
        _protect_generated_target(target)
        if _json_matches(target, payload):
            preserved.append(relative)
            continue
        atomic_write_json(target, payload)
        changed.append(relative)

    readout_target = root / READOUT_PATH
    _protect_generated_target(readout_target, markdown=True)
    readout = audit["humanSummary"]
    if readout_target.is_file() and readout_target.read_text(encoding="utf-8") == readout:
        preserved.append(READOUT_PATH)
    else:
        atomic_write_text(readout_target, readout)
        changed.append(READOUT_PATH)

    ratification_target = root / RATIFICATION_PATH
    _protect_generated_target(ratification_target, markdown=True)
    ratification_markdown = _render_ratification_packet(audit, plan["authorityBoundActions"])
    if ratification_target.is_file() and ratification_target.read_text(encoding="utf-8") == ratification_markdown:
        preserved.append(RATIFICATION_PATH)
    else:
        atomic_write_text(ratification_target, ratification_markdown)
        changed.append(RATIFICATION_PATH)

    verification = verify_governance_convergence(root)
    return {
        "status": "APPLIED_READY" if verification["status"] == "PASS" else "APPLIED_REVIEW_REQUIRED",
        "root": str(root),
        "writes": changed,
        "unchanged": preserved,
        "canonicalAuthoritiesModified": False,
        "authorityDriftRatification": ratification,
        "automaticActionsApplied": [item["id"] for item in plan["automaticActions"]],
        "authorityBoundActionsRemaining": plan["authorityBoundActions"],
        "verification": verification,
        "designGate": verification["designGate"],
        "finalizationReadiness": verification["finalizationReadiness"],
    }


def verify_governance_convergence(repository_root: str | Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    missing = [
        path
        for path in (MAP_PATH, ADAPTER_PATH, MANIFEST_PATH, READOUT_PATH, PLAN_PATH, RATIFICATION_PATH)
        if not (root / path).is_file()
    ]
    audit = audit_governance(root)
    manifest = read_json(root / MANIFEST_PATH, {}) or {}
    drift = audit["authorityDrift"]
    errors = [f"Missing generated governance artifact: {path}" for path in missing]
    if manifest.get("generatedBy") != GENERATOR:
        errors.append("Convergence manifest is missing or is not owned by Design Intelligence")
    if drift["status"] == "DRIFT_DETECTED":
        errors.extend(item["message"] for item in drift["findings"])
    if audit["designGate"]["status"] == "LOCKED":
        errors.append("Design remains locked until blocking governance findings are resolved")
    return {
        "status": "PASS" if not errors else "FAIL",
        "root": str(root),
        "artifactsPresent": not missing,
        "authorityDrift": drift,
        "designGate": audit["designGate"],
        "finalizationReadiness": audit["finalizationReadiness"],
        "errors": errors,
        "warnings": [item["message"] for item in audit["findings"] if item["severity"] == "P2"],
    }


def governance_design_preflight(repository_root: str | Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    governance_root = root / GOVERNANCE_ROOT
    if (root / MANIFEST_PATH).is_file() or governance_root.exists():
        verification = verify_governance_convergence(root)
        return {
            **verification,
            "status": (
                "PASS"
                if verification["status"] == "PASS"
                and verification["designGate"]["status"] == "READY"
                else "BLOCKED"
            ),
            "enforcementMode": "APPLIED_CONVERGENCE",
        }
    audit = audit_governance(root)
    if not audit["equivalentSystems"]:
        return {
            "status": "PASS",
            "enforcementMode": "ADVISORY_UNTIL_CONVERGENCE_APPLIED",
            "designGate": {
                "status": "ADVISORY",
                "reason": "No existing equivalent or applied convergence baseline was found. Run govern apply to establish enforcement.",
                "requiredBeforeDesign": audit["designGate"]["requiredBeforeDesign"],
            },
            "finalizationReadiness": audit["finalizationReadiness"],
            "warnings": [
                item["message"] for item in audit["findings"]
                if item["severity"] in BLOCKING_SEVERITIES
            ],
            "unbaselined": True,
        }
    return {
        "status": "PASS" if audit["designGate"]["status"] == "READY" else "BLOCKED",
        "enforcementMode": "EXISTING_SYSTEM",
        "designGate": audit["designGate"],
        "finalizationReadiness": audit["finalizationReadiness"],
        "errors": [item["message"] for item in audit["findings"] if item["severity"] in BLOCKING_SEVERITIES],
        "unbaselined": True,
    }


def render_governance_readout(report: dict[str, Any]) -> str:
    journey = report["journeyModel"]
    finalization = report["finalizationReadiness"]
    lines = [
        "<!-- generatedBy: design-intelligence-governance -->",
        "# Repository Understanding And Finalization Readout",
        "",
        "## Direct Answer",
        "",
        f"- Product understanding: **{finalization['understanding']}**",
        f"- Governance condition: **{finalization['governance']}**",
        f"- Finalization readiness: **{finalization['status']}**",
        f"- Design work: **{report['designGate']['status']}**",
        f"- User journey: **{journey['status']}**",
        f"- Journey verification: **{journey['proofStatus']}**",
        "",
        "## What Governs This Repository",
        "",
    ]
    for role, count in report["authoritySummary"].items():
        lines.append(f"- {role.replace('-', ' ').title()}: {count} tracked source{'s' if count != 1 else ''}")
    lines.extend(["", "## Existing Systems To Preserve", ""])
    if report["equivalentSystems"]:
        for system in report["equivalentSystems"]:
            lines.append(f"- **{system['name']}** ({system['status']}): {system['purpose']}")
    else:
        lines.append("- No complete equivalent governing system was detected; a repository-owned fallback must be ratified.")

    lines.extend(["", "## User Journey", ""])
    if journey["journeys"]:
        for item in journey["journeys"][:8]:
            lines.append(f"### {item['title']}")
            lines.append(f"Source: `{item['source']}`")
            for stages in item["stageChains"][:3]:
                lines.append(f"- {' -> '.join(stages)}")
            if item["routes"]:
                lines.append(f"- Product routes: {', '.join(f'`{route}`' for route in item['routes'][:12])}")
            if item["implementationPaths"]:
                lines.append(
                    "- Implementation links: "
                    + ", ".join(f"`{path}`" for path in item["implementationPaths"][:12])
                )
            lines.append("")
    else:
        lines.append("No governed user journey was found. Product-facing implementation must not proceed from design taste alone.")

    backlog = report["backlogModel"]
    lines.extend(["", "## Product Completion Backlog", ""])
    if backlog["itemCount"]:
        lines.append(f"- Total governed items found: **{backlog['itemCount']}**")
        for status, count in backlog["counts"].items():
            if count:
                lines.append(f"- {status.title()}: {count}")
        lines.append(f"- Items without an explicit journey stage: {len(backlog['itemsWithoutJourneyStage'])}")
        lines.append(f"- Items missing an outcome or success signal: {len(backlog['itemsMissingOutcome'])}")
        lines.append("")
        for item in backlog["items"][:20]:
            stages = ", ".join(item["journeyStages"]) or "not explicitly mapped"
            lines.append(
                f"- **{item['id']}** [{item['executionStatus']}]: {item['title']} | Journey: {stages}"
            )
    else:
        lines.append("- Backlog sources exist, but no supported item records were parsed. Completion remains undetermined.")

    lines.extend(["", "## Blocking Problems", ""])
    blocking = [item for item in report["findings"] if item["severity"] in BLOCKING_SEVERITIES]
    if blocking:
        for item in blocking:
            paths = f" ({', '.join(f'`{path}`' for path in item.get('paths', [])[:4])})" if item.get("paths") else ""
            lines.append(f"- **{item['severity']} {item['title']}**: {item['message']}{paths}")
    else:
        lines.append("- No blocking deterministic governance problem was detected.")

    lines.extend([
        "",
        "## What The Tool Will Do",
        "",
        "1. Preserve and bind existing authorities instead of replacing them.",
        "2. Create a derived authority map, repository adapter, human readout, and hash-bound convergence manifest.",
        "3. Stop on vision, architecture, security, ownership, or unresolved authority decisions.",
        "4. Detect later unreviewed changes to critical governing sources.",
        "5. Keep design locked until the repository can explain the actor, journey, truth, architecture, backlog, and proof path.",
        "6. Unlock design adoption only after governance convergence is verified.",
        "",
        "## Repository Structure",
        "",
    ])
    for item in report["implementationRoots"]:
        lines.append(f"- `{item['path']}`: {item['purpose']}")
    lines.extend([
        "",
        "This file is a generated navigation view. Existing repository authorities remain canonical.",
        "",
    ])
    return "\n".join(lines)


def _tracked_files(root: Path) -> tuple[list[str], str]:
    try:
        if not _is_git_root(root):
            raise subprocess.CalledProcessError(1, ["git", "rev-parse"])
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=True,
            capture_output=True,
        )
        paths = [item.decode("utf-8", errors="ignore") for item in result.stdout.split(b"\0") if item]
        return sorted(path for path in paths if not _is_ignored(path)), "git-tracked"
    except (OSError, subprocess.CalledProcessError):
        paths: list[str] = []
        for current, directories, files in os.walk(root):
            directories[:] = [item for item in directories if item not in IGNORED_DIRECTORIES]
            base = Path(current)
            for filename in files:
                relative = (base / filename).relative_to(root).as_posix()
                if not _is_ignored(relative):
                    paths.append(relative)
        return sorted(paths), "filesystem-fallback"


def _untracked_authority_candidates(root: Path) -> list[dict[str, Any]]:
    if not _is_git_root(root):
        return []
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--others", "--exclude-standard", "-z"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    candidates: list[dict[str, Any]] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8", errors="ignore")
        roles = _roles_for_path(relative)
        is_direct_authority = Path(relative).name.lower() in {
            "agents.md", "claude.md", "skill.md", ".cursorrules", ".windsurfrules"
        }
        is_hook = relative.startswith((".husky/", ".githooks/"))
        is_governance_document = relative.startswith("docs/governance/")
        if roles and not _is_ignored(relative) and (
            is_direct_authority or is_hook or is_governance_document
        ):
            candidates.append({"path": relative, "roles": roles, "reason": "Untracked files cannot govern other agents."})
    return sorted(candidates, key=lambda item: item["path"])


def _is_git_root(root: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    try:
        return Path(result.stdout.strip()).resolve() == root.resolve()
    except OSError:
        return False


def _authority_records(root: Path, tracked: Iterable[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for relative in tracked:
        roles = _roles_for_path(relative)
        if not roles:
            continue
        path = root / relative
        if not path.is_file():
            continue
        text = _read_authority_text(path)
        lifecycle = _lifecycle(relative, text, root)
        records.append({
            "path": relative,
            "sha256": _sha256_file(path),
            "roles": roles,
            "scope": _scope_for(relative, roles),
            "lifecycle": lifecycle,
            "authorityLevel": _authority_level(relative, text, lifecycle),
            "declaresAuthority": bool(re.search(r"\b(binding|canonical|authoritative|source of truth|governing)\b", text, re.I)),
        })
    return sorted(records, key=lambda item: item["path"])


def _roles_for_path(relative: str) -> list[str]:
    lowered = relative.lower()
    name = Path(lowered).name
    suffix = Path(lowered).suffix
    roles: set[str] = set()
    if suffix not in TEXT_SUFFIXES and not _is_governance_script(lowered):
        return []
    if name in {"agents.md", "claude.md", ".cursorrules", ".windsurfrules"} or "copilot-instructions" in lowered:
        roles.add("instructions")
    if "/skills/" in f"/{lowered}" and name in {"skill.md", "agents.md"}:
        roles.add("skills")
    if lowered.startswith((".husky/", ".githooks/")) or name in {"lefthook.yml", "lefthook.yaml", ".pre-commit-config.yaml"}:
        roles.add("hooks")
    if name in {"package.json", "pyproject.toml", "cargo.toml", "go.mod"}:
        roles.update({"contracts", "delivery"})
    if "backlog" in lowered or "/roadmap" in lowered or name.startswith("roadmap"):
        roles.add("backlog")
    if re.search(r"(^|/)(adr[-_/]|architecture/adr/|decisions?/)", lowered) or re.search(r"(^|/)\d{4}-.+\.md$", lowered):
        roles.update({"adrs", "architecture"})
    if any(token in lowered for token in ("architecture", "system-context", "bounded-context", "topology", "module-boundar")):
        roles.add("architecture")
    if any(token in lowered for token in ("governance", "policy", "authority", "charter", "control-plane", "agentic-framework")):
        roles.add("governance")
    if any(token in lowered for token in ("security", "authorization", "permission", "tenant-isolation", "threat-model", "data-protection")):
        roles.add("security")
    if any(token in lowered for token in ("journey", "workflow", "golden-path", "commercial-spine", "user-manual", "lifecycle")):
        roles.add("journeys")
    if any(token in lowered for token in ("persona", "actor", "role-capability", "user-role")):
        roles.add("personas")
    if any(token in lowered for token in ("requirement", "specification", "capabilit", "product-boundary", "platform-spec")):
        roles.add("requirements")
    if any(token in lowered for token in ("vision", "mission", "strategy", "north-star", "core-promise", "platform-spec")):
        roles.add("vision")
    if "principle" in lowered or "invariant" in lowered:
        roles.add("principles")
    if any(token in lowered for token in ("metric", "kpi", "success-measure", "benchmark")):
        roles.add("metrics")
    if "experiment" in lowered or "hypothesis" in lowered:
        roles.add("experiments")
    if any(token in lowered for token in ("contract", "schema", "data-model", "event-catalog", "api-convention", "api-contract")):
        roles.add("contracts")
    if any(token in lowered for token in ("design", "ui-ux", "component-register", "tokens", "accessibility", "surface-register")):
        roles.add("design")
    if any(token in lowered for token in ("release", "deploy", "runbook", "rollback", "readiness", "prepush", "pre-push", "ci.")):
        roles.add("delivery")
    if any(token in lowered for token in ("incident", "audit", "evidence", "outcome", "handoff", "retrospective")):
        roles.add("evidence")
    if any(token in lowered for token in ("test", "spec.", "playwright", "cypress", "vitest", "jest")):
        roles.add("tests")
    if lowered in {".dev/intent-index.json"}:
        roles.update({"vision", "principles", "personas", "requirements", "journeys", "metrics", "experiments"})
    if lowered in {"devctl.yaml", ".dev/model-routing.json", ".dev/standards-profile.json"}:
        roles.add("governance")
    if lowered == "docs/atlas/atlas-manifest.yaml":
        roles.update({"governance", "architecture"})
    return sorted(roles)


def _is_governance_script(lowered: str) -> bool:
    if not lowered.startswith("scripts/"):
        return False
    return any(token in lowered for token in ("check-", "verify-", "release", "prepush", "post-", "milestone", "governance", "audit"))


def _read_authority_text(path: Path) -> str:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:192_000]
    except OSError:
        return ""


def _lifecycle(relative: str, text: str, root: Path) -> str:
    lowered = relative.lower()
    head = "\n".join(text.splitlines()[:100]).lower()
    if any(token in lowered for token in ("/archive/", "/historical/", "/deprecated/", "/exports/")):
        return "historical"
    if relative == "docs/backlog.md" and ((root / "docs/backlog-now.md").is_file() or (root / "docs/backlog-next.md").is_file()):
        return "historical"
    if re.search(r"\b(historical reference only|non-authoritative|status:\s*superseded|status:\s*deprecated)\b", head):
        return "historical"
    if re.search(r"\b(status:\s*(draft|proposed|experimental)|draft specification)\b", head):
        return "proposed"
    if "/audits/" in lowered or "/evidence/" in lowered or "/reports/" in lowered:
        return "evidence"
    if re.search(r"\b(binding contract|status:\s*(active|accepted|current)|canonical truth|source of truth)\b", head):
        return "active"
    return "candidate"


def _authority_level(relative: str, text: str, lifecycle: str) -> str:
    if lifecycle in {"historical", "evidence"}:
        return "evidence"
    if re.search(r"\b(binding contract|canonical|source of truth|authoritative|governing document)\b", text[:32_000], re.I):
        return "binding"
    if relative in {"AGENTS.md", "CLAUDE.md"}:
        return "binding"
    return "candidate"


def _scope_for(relative: str, roles: list[str]) -> str:
    path = Path(relative)
    if "skills" in roles:
        return f"skill:{path.parent.name}"
    if "instructions" in roles:
        parent = path.parent.as_posix()
        return "repository" if parent == "." else f"path:{parent}"
    if len(path.parts) >= 2 and path.parts[0] == "docs":
        return f"domain:{path.parts[1]}"
    return "repository"


def _group_records(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record["lifecycle"] == "historical":
            continue
        for role in record["roles"]:
            grouped[role].append(record)
    return {role: items for role, items in grouped.items()}


def _detect_equivalent_systems(root: Path, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    systems: list[dict[str, Any]] = []
    paths = {item["path"] for item in records if item["lifecycle"] != "historical"}
    atlas_required = {
        "docs/atlas/atlas-manifest.yaml",
        "docs/atlas/00-governance/source-authority.md",
        "docs/atlas/04-workflows/workflow-register.yaml",
        "docs/atlas/10-design-system/component-register.yaml",
    }
    if atlas_required.issubset(paths):
        manifest_text = _read_authority_text(root / "docs/atlas/atlas-manifest.yaml")
        partial = bool(re.search(r"\bpending_|remaining_prompt_range|unresolved:\s*[1-9]", manifest_text, re.I))
        systems.append({
            "id": "enterprise-atlas",
            "name": "Repository Enterprise Atlas",
            "status": "PARTIAL" if partial else "READY",
            "purpose": "Existing governance, actors, workflows, architecture, security, design, dependency, and gap model.",
            "bindings": sorted(atlas_required),
        })
    if {"devctl.yaml", ".dev/intent-index.json", ".dev/standards-profile.json", ".dev/model-routing.json"}.issubset(paths):
        systems.append({
            "id": "development-control-plane",
            "name": "Repository Development Control Plane",
            "status": "READY",
            "purpose": "Existing intent, architecture, intelligence, backlog, context, and verification coordination.",
            "bindings": ["devctl.yaml", ".dev/intent-index.json", ".dev/standards-profile.json", ".dev/model-routing.json"],
        })
    skill_roots = sorted({str(Path(path).parents[1]) for path in paths if path.endswith("/SKILL.md") and "/skills/" in f"/{path}"})
    if "AGENTS.md" in paths and skill_roots:
        systems.append({
            "id": "agent-governance",
            "name": "Repository Agent Governance",
            "status": "READY",
            "purpose": "Existing root instructions and scoped specialist skills.",
            "bindings": ["AGENTS.md", *skill_roots],
        })
    design_bindings = [
        path for path in (
            "docs/atlas/10-design-system/component-register.yaml",
            "docs/atlas/10-design-system/tokens.md",
            "apps/web/app/globals.css",
            ".design/memory/component-registry.json",
        ) if (root / path).is_file()
    ]
    if len(design_bindings) >= 2:
        systems.append({
            "id": "design-system",
            "name": "Repository Design System",
            "status": "READY",
            "purpose": "Existing token, component, interaction, accessibility, and design-governance authority.",
            "bindings": design_bindings,
        })
    return systems


def _extract_journeys(root: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    journeys: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda item: (item["authorityLevel"] != "binding", item["path"])):
        path = root / record["path"]
        text = _read_authority_text(path)
        chains = _stage_chains(text)
        is_index = record["path"] == ".dev/intent-index.json"
        indexed_journeys = _indexed_journeys(path) if is_index else []
        if not chains and not is_index and record["authorityLevel"] != "binding":
            continue
        title = _first_heading(text) or Path(record["path"]).stem.replace("-", " ").title()
        routes = sorted(set(re.findall(r"`(/(?!/)[A-Za-z0-9_\-./\[\]]+)`", text)))
        route_values = [value[0] if isinstance(value, tuple) else value for value in routes]
        implementation = sorted(set(re.findall(
            r"`((?:apps|packages|src|components|scripts|e2e|tests)/[A-Za-z0-9_@.\-/\[\]]+)`",
            text,
        )))
        test_paths = [item for item in implementation if re.search(r"(?:test|spec|e2e)", item, re.I)]
        if indexed_journeys:
            test_paths.extend(
                path
                for item in indexed_journeys
                for path in item.get("tests", [])
                if isinstance(path, str)
            )
        journeys.append({
            "title": title,
            "source": record["path"],
            "binding": record["authorityLevel"] == "binding" or is_index,
            "stageChains": chains,
            "routes": route_values,
            "implementationPaths": implementation,
            "testPaths": test_paths,
            "existingTestPaths": [item for item in test_paths if (root / item).is_file()],
        })
        if len(journeys) >= 24:
            break
    binding = [item for item in journeys if item["binding"]]
    primary = next((item for item in binding if item["stageChains"]), binding[0] if binding else None)
    primary_tests = sorted(primary["existingTestPaths"] if primary else [])
    supporting_tests = sorted({path for item in journeys for path in item["existingTestPaths"]})
    e2e_scripts = _e2e_script_targets(root)
    executable_e2e = [
        item for item in e2e_scripts
        if item["script"].lower().startswith("test:e2e")
        and ":install" not in item["script"].lower()
        and item["targetsExist"]
        and any(re.search(r"(?:e2e|spec|test)\.", target, re.I) for target in item["targets"])
    ]
    status = "DEFINED" if binding else "PARTIAL" if journeys else "MISSING"
    if status == "MISSING":
        proof = "MISSING"
    else:
        proof = "LINKED" if primary_tests or executable_e2e else "FRAGMENTED" if supporting_tests or e2e_scripts else "MISSING"
    return {
        "status": status,
        "proofStatus": proof,
        "journeys": journeys,
        "bindingJourneyCount": len(binding),
        "linkedTests": primary_tests,
        "supportingTests": supporting_tests,
        "e2eScriptTargets": e2e_scripts,
    }


def _indexed_journeys(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    journeys = payload.get("journeys", []) if isinstance(payload, dict) else []
    return [item for item in journeys if isinstance(item, dict)]


def _stage_chains(text: str) -> list[list[str]]:
    chains: list[list[str]] = []
    for line in text.splitlines():
        if "->" not in line and "→" not in line:
            continue
        cleaned = re.sub(r"^[^:`]{0,40}:\s*", "", line.strip())
        cleaned = cleaned.strip("`*_ -")
        stages = [re.sub(r"[`*_]", "", item).strip() for item in re.split(r"\s*(?:->|→)\s*", cleaned)]
        stages = [item for item in stages if item and len(item) <= 80]
        if len(stages) >= 3 and stages not in chains:
            chains.append(stages)
    return chains[:8]


def _first_heading(text: str) -> str | None:
    for line in text.splitlines()[:80]:
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _audit_package_scripts(root: Path, tracked: Iterable[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for relative in tracked:
        if not relative.endswith("package.json") or _is_ignored(relative):
            continue
        package_path = root / relative
        try:
            package = json.loads(package_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        scripts = package.get("scripts", {}) if isinstance(package, dict) else {}
        if not isinstance(scripts, dict):
            continue
        base = package_path.parent
        for name, command in scripts.items():
            if not isinstance(command, str):
                continue
            for target in _literal_script_targets(command):
                candidate = (base / target).resolve()
                try:
                    display = candidate.relative_to(root).as_posix()
                except ValueError:
                    continue
                if candidate.is_file():
                    continue
                severity = "P1" if re.search(r"(^|:)(test|check|verify|release|prepush|precommit|e2e)", name) else "P2"
                findings.append({
                    "package": relative,
                    "script": name,
                    "target": display,
                    "severity": severity,
                    "command": command,
                })
    unique = {(item["package"], item["script"], item["target"]): item for item in findings}
    return sorted(unique.values(), key=lambda item: (item["severity"], item["package"], item["script"]))


def _literal_script_targets(command: str) -> list[str]:
    pattern = re.compile(
        r"(?<![A-Za-z0-9_@.-])((?:\./)?(?:scripts|e2e|tests|test|playwright|config)/[A-Za-z0-9_@./\[\]-]+\.(?:json|ya?ml|[cm]?[jt]sx?|py))(?=$|[\s'\"])"
    )
    return sorted(set(match.group(1).removeprefix("./") for match in pattern.finditer(command)))


def _e2e_script_targets(root: Path) -> list[dict[str, Any]]:
    package = read_json(root / "package.json", {}) or {}
    scripts = package.get("scripts", {}) if isinstance(package, dict) else {}
    targets: list[dict[str, Any]] = []
    for name, command in scripts.items() if isinstance(scripts, dict) else []:
        if "e2e" not in name.lower() and "playwright" not in str(command).lower():
            continue
        literal = _literal_script_targets(str(command))
        targets.append({
            "script": name,
            "targets": literal,
            "targetsExist": all((root / item).is_file() for item in literal),
        })
    return targets


def _build_findings(
    root: Path,
    records: list[dict[str, Any]],
    by_role: dict[str, list[dict[str, Any]]],
    equivalents: list[dict[str, Any]],
    journeys: dict[str, Any],
    backlog: dict[str, Any],
    script_damage: list[dict[str, Any]],
    untracked: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for role in sorted(CORE_UNDERSTANDING_ROLES):
        if by_role.get(role):
            continue
        findings.append(_finding(
            f"MISSING-{role.upper()}",
            "P0" if role in {"instructions", "vision", "journeys"} else "P1",
            role,
            f"Missing {role.replace('-', ' ')} authority",
            f"The repository cannot explain its {role.replace('-', ' ')} from tracked governing evidence.",
            "ADD_AND_RATIFY_AUTHORITY",
        ))

    if journeys["status"] == "PARTIAL":
        findings.append(_finding(
            "JOURNEY-NOT-BINDING", "P1", "journey", "User journey is not binding",
            "Journey material exists, but no source clearly governs implementation priorities and completion.",
            "RATIFY_EXISTING_JOURNEY", paths=[item["source"] for item in journeys["journeys"][:6]],
        ))
    if journeys["proofStatus"] != "LINKED":
        findings.append(_finding(
            "JOURNEY-PROOF-FRAGMENTED", "P1", "journey", "End-to-end journey proof is incomplete",
            "The product journey is documented but is not linked to one current executable end-to-end proof path.",
            "BUILD_OR_BIND_JOURNEY_PROOF", paths=[item["source"] for item in journeys["journeys"][:4]],
        ))

    if backlog["itemCount"] and backlog["itemsMissingOutcome"]:
        findings.append(_finding(
            "BACKLOG-OUTCOMES-MISSING", "P1", "backlog", "Backlog items lack product outcomes",
            f"{len(backlog['itemsMissingOutcome'])} active or staged item(s) do not declare an actor-facing outcome.",
            "ADD_OUTCOME_AND_SUCCESS_SIGNAL", paths=backlog["itemsMissingOutcome"][:20],
        ))

    for item in script_damage:
        findings.append(_finding(
            f"BROKEN-SCRIPT-{_slug(item['script'])}", item["severity"], "damaged-control",
            f"Package command {item['script']} targets a missing file",
            f"The command cannot run as declared because {item['target']} does not exist.",
            "REPAIR_EXISTING_COMMAND_OR_TARGET", paths=[item["package"], item["target"]],
        ))

    skill_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in by_role.get("skills", []):
        if Path(record["path"]).name.lower() != "skill.md":
            continue
        skill_groups[record["scope"]].append(record)
    for scope, items in skill_groups.items():
        hashes = {item["sha256"] for item in items}
        if len(items) > 1 and len(hashes) > 1:
            findings.append(_finding(
                f"SKILL-CONFLICT-{_slug(scope)}", "P1", "authority-conflict",
                f"Conflicting instructions exist for {scope}",
                "The same scoped skill has different tracked definitions. Agents may behave differently by adapter.",
                "CONVERGE_SCOPED_SKILL", paths=[item["path"] for item in items],
            ))

    if untracked:
        findings.append(_finding(
            "UNTRACKED-AUTHORITY", "P1", "authority-conflict", "Untracked governing files are present",
            "Instructions or skills that are not tracked cannot reliably govern future agents or releases.",
            "ADOPT_OR_REMOVE_UNTRACKED_AUTHORITY", paths=[item["path"] for item in untracked[:20]],
        ))

    for system in equivalents:
        if system["status"] != "READY":
            findings.append(_finding(
                f"INCOMPLETE-{system['id'].upper()}", "P1", "governance-conflict",
                f"{system['name']} is incomplete",
                "The repository already has an equivalent governing model, but its own manifest records pending or unresolved work.",
                "COMPLETE_EXISTING_GOVERNANCE_SYSTEM", paths=system["bindings"],
            ))

    conflict_sources = [
        record for record in records
        if "governance" in record["roles"] and "conflict" in record["path"].lower()
    ]
    for record in conflict_sources:
        text = _read_authority_text(root / record["path"])
        unresolved = len(re.findall(r"^\s*status:\s*(?:open_drift|human_decision_required)\s*$", text, re.I | re.M))
        if unresolved:
            findings.append(_finding(
                f"OPEN-CONFLICTS-{_slug(record['path'])}", "P1", "governance-conflict",
                "Governing conflict register contains unresolved decisions",
                f"{unresolved} conflict record(s) remain open or require a human decision.",
                "RESOLVE_OR_AUTHORITATIVELY_HOLD_CONFLICTS", paths=[record["path"]],
            ))
    return findings


def _audit_authority_drift(root: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    manifest = read_json(root / MANIFEST_PATH, {}) or {}
    previous = manifest.get("criticalAuthorities", []) if isinstance(manifest, dict) else []
    current_state_sha256 = _critical_authority_state_sha256(records)
    if not previous:
        return {
            "status": "UNBASELINED",
            "changed": [],
            "missing": [],
            "added": [],
            "currentAuthorityStateSha256": current_state_sha256,
            "findings": [],
        }
    current = {
        item["path"]: item for item in records
        if set(item["roles"]) & CRITICAL_ROLES and item["lifecycle"] not in {"historical", "evidence"}
    }
    expected = {item["path"]: item for item in previous if isinstance(item, dict) and item.get("path")}
    changed = sorted(path for path in expected.keys() & current.keys() if expected[path].get("sha256") != current[path]["sha256"])
    missing = sorted(expected.keys() - current.keys())
    added = sorted(current.keys() - expected.keys())
    findings: list[dict[str, Any]] = []
    if changed or missing:
        findings.append(_finding(
            "CRITICAL-AUTHORITY-DRIFT", "P1", "vision", "Critical governing authority changed",
            "Vision, instruction, journey, architecture, backlog, security, or design authority changed after convergence and requires review.",
            "REVIEW_AND_RATIFY_AUTHORITY_CHANGE", paths=[*changed, *missing],
        ))
    return {
        "status": "DRIFT_DETECTED" if changed or missing else "ADDITIONS_DETECTED" if added else "STABLE",
        "changed": changed,
        "missing": missing,
        "added": added,
        "currentAuthorityStateSha256": current_state_sha256,
        "findings": findings,
    }


def _finalization_readiness(
    by_role: dict[str, list[dict[str, Any]]],
    journeys: dict[str, Any],
    equivalents: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    missing_core = [role for role in CORE_UNDERSTANDING_ROLES if not by_role.get(role)]
    p0 = [item["id"] for item in findings if item["severity"] == "P0"]
    p1 = [item["id"] for item in findings if item["severity"] == "P1"]
    if p0 or missing_core:
        status = "UNDERSTANDING_INCOMPLETE"
    elif p1:
        status = "GOVERNANCE_CONFLICTED"
    elif journeys["proofStatus"] != "LINKED":
        status = "EXECUTION_READY"
    else:
        status = "DESIGN_READY"
    return {
        "status": status,
        "understanding": "INCOMPLETE" if missing_core else "MAPPED",
        "governance": "CONFLICTED" if p0 or p1 else "COHERENT",
        "missingCoreRoles": sorted(missing_core),
        "blockingFindings": [*p0, *p1],
        "existingSystemStrategy": "PRESERVE_AND_BIND" if equivalents else "ADD_RATIFIED_FALLBACK",
        "completionClaimed": False,
    }


def _backlog_summary(
    root: Path,
    records: list[dict[str, Any]],
    journeys: dict[str, Any],
) -> dict[str, Any]:
    active = [item["path"] for item in records if item["lifecycle"] in {"active", "candidate"}]
    historical = [item["path"] for item in records if item["lifecycle"] == "historical"]
    canonical = [item["path"] for item in records if item["authorityLevel"] == "binding"]
    primary_stages = next(
        (
            chain
            for journey in journeys["journeys"]
            if journey["binding"]
            for chain in journey["stageChains"]
        ),
        [],
    )
    items: list[dict[str, Any]] = []
    for record in records:
        if record["lifecycle"] == "historical" or not record["path"].endswith((".md", ".mdx")):
            continue
        role = "staged" if "next" in Path(record["path"]).stem.lower() else "active"
        items.extend(_parse_markdown_backlog(root / record["path"], record["path"], role, primary_stages))
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for item in items:
        unique[(item["source"], item["id"])] = item
    items = sorted(unique.values(), key=lambda item: (item["sourceRole"] != "active", item["id"]))
    counts = {
        status: sum(item["executionStatus"] == status for item in items)
        for status in ("ACTIVE", "PARTIAL", "BLOCKED", "STAGED", "DEFERRED", "COMPLETED")
    }
    missing_outcome = [
        f"{item['source']}#{item['id']}"
        for item in items
        if item["executionStatus"] != "COMPLETED"
        if not item["hasOutcome"] or not item["hasSuccessSignal"]
    ]
    unmapped = [
        item["id"]
        for item in items
        if item["executionStatus"] != "COMPLETED" and not item["journeyStages"]
    ]
    return {
        "status": "MAPPED" if active else "MISSING",
        "activeSources": active,
        "canonicalSources": canonical,
        "historicalSources": historical,
        "itemCount": len(items),
        "counts": counts,
        "items": items,
        "itemsMissingOutcome": missing_outcome,
        "itemsWithoutJourneyStage": unmapped,
        "completion": (
            "IN_PROGRESS"
            if any(item["executionStatus"] != "COMPLETED" for item in items)
            else "COMPLETE" if items else "NOT_DETERMINED"
        ),
        "introduceParallelBacklog": False,
    }


def _parse_markdown_backlog(
    path: Path,
    source: str,
    role: str,
    journey_stages: list[str],
) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    matches = list(re.finditer(
        r"^###\s+[^A-Za-z0-9\n]*([A-Za-z][A-Za-z0-9-]*-\d+[A-Za-z]?):\s+(.+?)\s*$",
        text,
        re.MULTILINE,
    ))
    items: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end():body_end]
        prior = text[:match.start()]
        section_matches = list(re.finditer(r"^(?:##|####)\s+(.+?)\s*$", prior, re.MULTILINE))
        section = section_matches[-1].group(1).strip() if section_matches else ""
        lowered_section = section.lower()
        if "active gate pointer" in lowered_section:
            continue
        status_text = " ".join(re.findall(
            r"^-\s+(?:Status|Classification|Priority|Current bounded scope):\s*(.+)$",
            body,
            re.MULTILINE | re.IGNORECASE,
        ))
        lowered_status = status_text.lower()
        if any(token in lowered_section for token in ("recently closed", "archived", "verification evidence")) or any(
            token in lowered_status for token in ("archive", "closed", "completed")
        ):
            execution = "COMPLETED"
        elif any(token in lowered_status for token in ("externally blocked", "blocked", "human checkpoint", "approval-gated")):
            execution = "BLOCKED"
        elif "deferred" in lowered_status:
            execution = "DEFERRED"
        elif role == "staged":
            execution = "STAGED"
        elif any(token in lowered_status for token in ("partial", "bounded scope", "locally", "remaining")):
            execution = "PARTIAL"
        else:
            execution = "ACTIVE"
        body_lower = body.lower()
        mapped_stages = [
            stage
            for stage in journey_stages
            if re.search(rf"\b{re.escape(stage.lower())}\b", body_lower)
        ]
        items.append({
            "id": match.group(1),
            "title": match.group(2).strip(),
            "source": source,
            "sourceRole": role,
            "section": section,
            "executionStatus": execution,
            "statusEvidence": status_text[:500],
            "hasOutcome": bool(re.search(r"^-\s+Outcome:\s*\S", body, re.MULTILINE | re.IGNORECASE)),
            "hasSuccessSignal": bool(re.search(r"^-\s+Success signal:\s*\S", body, re.MULTILINE | re.IGNORECASE)),
            "hasEvidenceBoundary": bool(re.search(r"^-\s+Evidence or assumption:\s*\S", body, re.MULTILINE | re.IGNORECASE)),
            "journeyStages": mapped_stages,
        })
    return items


def _implementation_roots(root: Path) -> list[dict[str, str]]:
    package = read_json(root / "package.json", {}) or {}
    workspace_patterns = package.get("workspaces", []) if isinstance(package, dict) else []
    roots: list[dict[str, str]] = []
    if isinstance(workspace_patterns, dict):
        workspace_patterns = workspace_patterns.get("packages", [])
    for pattern in workspace_patterns if isinstance(workspace_patterns, list) else []:
        if not isinstance(pattern, str):
            continue
        base = pattern.split("*")[0].rstrip("/")
        if base and (root / base).is_dir():
            roots.append({"path": base, "purpose": "Repository workspace root"})
    purposes = {
        "apps/web": "User interface and web API",
        "apps/worker": "Background and integration processing",
        "packages/domain": "Business rules and invariants",
        "packages/application": "Use cases and workflow coordination",
        "packages/contracts": "Shared data and event contracts",
        "packages/db": "Persistence schema and migrations",
        "packages/infrastructure": "Provider and infrastructure adapters",
        "src": "Primary application source",
        "app": "Application routes and surfaces",
        "components": "Shared interface components",
        "docs": "Product, architecture, governance, and delivery authority",
        "scripts": "Verification, automation, and release controls",
    }
    for path, purpose in purposes.items():
        if (root / path).exists() and path not in {item["path"] for item in roots}:
            roots.append({"path": path, "purpose": purpose})
    return roots


def _build_repository_adapter(root: Path, audit: dict[str, Any]) -> dict[str, Any]:
    role_bindings: dict[str, list[str]] = defaultdict(list)
    for item in audit["authorities"]:
        if item["lifecycle"] in {"historical", "evidence"}:
            continue
        for role in item["roles"]:
            role_bindings[role].append(item["path"])
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedBy": GENERATOR,
        "mode": "EQUIVALENT_SYSTEM" if audit["equivalentSystems"] else "RATIFIED_FALLBACK_REQUIRED",
        "repository": root.name,
        "authorityBindings": {role: sorted(paths) for role, paths in sorted(role_bindings.items())},
        "equivalentSystems": audit["equivalentSystems"],
        "implementationRoots": audit["implementationRoots"],
        "backlog": audit["backlogModel"],
        "journeys": [
            {"title": item["title"], "source": item["source"], "binding": item["binding"]}
            for item in audit["journeyModel"]["journeys"]
        ],
        "designGate": audit["designGate"],
        "canonicalAuthorityModified": False,
    }


def _build_convergence_manifest(
    root: Path,
    audit: dict[str, Any],
    ratification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    critical = [
        {
            "path": item["path"],
            "sha256": item["sha256"],
            "roles": item["roles"],
            "scope": item["scope"],
            "lifecycle": item["lifecycle"],
        }
        for item in audit["authorities"]
        if set(item["roles"]) & CRITICAL_ROLES and item["lifecycle"] not in {"historical", "evidence"}
    ]
    existing = read_json(root / MANIFEST_PATH, {}) or {}
    created_at = existing.get("createdAt") if existing.get("generatedBy") == GENERATOR else None
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedBy": GENERATOR,
        "repository": root.name,
        "createdAt": created_at or datetime.now(timezone.utc).isoformat(),
        "criticalAuthorities": critical,
        "criticalAuthorityCount": len(critical),
        "designGateAtCreation": audit["designGate"],
        "criticalAuthoritySha256": _digest(critical),
        "ratificationClaimed": ratification is not None,
        "lastAuthorityDriftRatification": ratification,
        "canonicalAuthorityModified": False,
    }


def _validate_authority_drift_ratification(
    root: Path,
    audit: dict[str, Any],
    ratification_path: str | Path | None,
) -> dict[str, Any] | None:
    drift = audit["authorityDrift"]
    if drift["status"] != "DRIFT_DETECTED":
        if ratification_path is not None:
            raise ValueError("Authority-drift ratification was supplied, but no changed or missing authority was detected")
        return None
    if ratification_path is None:
        raise ValueError(
            "Critical authority drift cannot be rebaselined by apply. "
            "A repository owner must provide an exact authority-drift ratification receipt."
        )
    receipt_path = Path(ratification_path)
    if not receipt_path.is_absolute():
        receipt_path = root / receipt_path
    receipt = read_json(receipt_path.resolve(), {}) or {}
    required_paths = sorted([*drift["changed"], *drift["missing"]])
    receipt_paths = sorted(receipt.get("paths", [])) if isinstance(receipt.get("paths"), list) else []
    errors: list[str] = []
    if receipt.get("kind") != "AuthorityDriftRatification":
        errors.append("kind must be AuthorityDriftRatification")
    if receipt.get("decision") != "ACCEPT_AUTHORITY_DRIFT":
        errors.append("decision must be ACCEPT_AUTHORITY_DRIFT")
    if receipt.get("authority") != "repository-owner":
        errors.append("authority must be repository-owner")
    approved_by = receipt.get("approvedBy")
    if not isinstance(approved_by, str) or not approved_by.strip():
        errors.append("approvedBy is required")
    if receipt_paths != required_paths:
        errors.append("paths must exactly match the currently changed and missing critical authorities")
    if receipt.get("authorityStateSha256") != drift["currentAuthorityStateSha256"]:
        errors.append("authorityStateSha256 does not match the current critical authority state")
    reason = receipt.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        errors.append("reason is required")
    approved_at = receipt.get("approvedAt")
    try:
        parsed_at = datetime.fromisoformat(str(approved_at).replace("Z", "+00:00"))
        if parsed_at.tzinfo is None:
            raise ValueError
    except ValueError:
        errors.append("approvedAt must be an ISO-8601 timestamp with a timezone")
    if errors:
        raise ValueError("Invalid authority-drift ratification: " + "; ".join(errors))
    return {
        "kind": receipt["kind"],
        "decision": receipt["decision"],
        "authority": receipt["authority"],
        "approvedBy": approved_by.strip(),
        "approvedAt": approved_at,
        "reason": reason.strip(),
        "paths": receipt_paths,
        "authorityStateSha256": receipt["authorityStateSha256"],
        "receiptPath": receipt_path.resolve().relative_to(root).as_posix()
        if receipt_path.resolve().is_relative_to(root)
        else str(receipt_path.resolve()),
    }


def _critical_authority_state_sha256(records: list[dict[str, Any]]) -> str:
    state = [
        {"path": item["path"], "sha256": item["sha256"]}
        for item in records
        if set(item["roles"]) & CRITICAL_ROLES
        and item["lifecycle"] not in {"historical", "evidence"}
    ]
    return _digest(sorted(state, key=lambda item: item["path"]))


def _map_payload(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in audit.items()
        if key not in {"authorityDrift", "humanSummary", "observedAt", "reportSha256"}
    }


def _rehabilitation_payload(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedBy": GENERATOR,
        "status": plan["status"],
        "root": plan["root"],
        "finalizationReadiness": plan["finalizationReadiness"],
        "designGate": plan["designGate"],
        "automaticActions": plan["automaticActions"],
        "authorityBoundActions": plan["authorityBoundActions"],
        "executionBoundary": (
            "Derived bindings may be applied automatically. Product vision, architecture, security, "
            "ownership, release, and canonical backlog decisions require repository authority."
        ),
    }


def _render_ratification_packet(
    audit: dict[str, Any],
    actions: list[dict[str, Any]],
) -> str:
    lines = [
        "<!-- generatedBy: design-intelligence-governance -->",
        "# Repository Owner Ratification Packet",
        "",
        "This packet does not record approval. It identifies decisions that must be made before the repository can finalize the product and unlock design.",
        "",
        f"Current finalization readiness: **{audit['finalizationReadiness']['status']}**",
        f"Current design gate: **{audit['designGate']['status']}**",
        "",
        "## Decisions Required",
        "",
    ]
    if actions:
        for action in actions:
            target = action["target"]
            if isinstance(target, list):
                target_text = ", ".join(f"`{item}`" for item in target[:8]) or "repository authority"
            else:
                target_text = f"`{target}`"
            lines.extend([
                f"### {action['id']}",
                f"- Required action: **{action['action']}**",
                f"- Why: {action['reason']}",
                f"- Evidence: {target_text}",
                f"- Decision authority: {action.get('authority', 'repository-owner')}",
                "- Decision: PENDING",
                "",
            ])
    else:
        lines.append("No blocking owner ratification is currently required.")
    lines.extend([
        "## Ratification Boundary",
        "",
        "A human decision must be recorded through the repository's existing decision process. Editing this generated packet does not change authority, approve a design, close backlog work, or authorize merge, deployment, release, provider mutation, or baseline changes.",
        "",
    ])
    return "\n".join(lines)


def _protect_generated_target(path: Path, *, markdown: bool = False) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8", errors="ignore")
    if markdown:
        if "generatedBy: design-intelligence-governance" not in text[:200]:
            raise ValueError(f"Refusing to overwrite non-generated authority: {path}")
        return
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"Refusing to overwrite non-generated authority: {path}") from error
    if payload.get("generatedBy") != GENERATOR:
        raise ValueError(f"Refusing to overwrite non-generated authority: {path}")


def _json_matches(path: Path, payload: dict[str, Any]) -> bool:
    if not path.is_file():
        return False
    try:
        return json.loads(path.read_text(encoding="utf-8")) == payload
    except (OSError, json.JSONDecodeError):
        return False


def _finding(
    identifier: str,
    severity: str,
    category: str,
    title: str,
    message: str,
    required_action: str,
    *,
    paths: list[str] | None = None,
    authority: str = "repository-owner",
) -> dict[str, Any]:
    return {
        "id": identifier,
        "severity": severity,
        "category": category,
        "title": title,
        "message": message,
        "requiredAction": required_action,
        "paths": paths or [],
        "authority": authority,
    }


def _finding_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    return ({"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(item["severity"], 9), item["id"])


def _finding_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    return {severity: sum(item["severity"] == severity for item in findings) for severity in ("P0", "P1", "P2", "P3")}


def _design_gate_reason(findings: list[dict[str, Any]], finalization: dict[str, Any]) -> str:
    blocking = [item for item in findings if item["severity"] in BLOCKING_SEVERITIES]
    if blocking:
        return f"{len(blocking)} blocking governance or understanding problem(s) must be resolved before design adoption."
    return f"Repository is {finalization['status'].lower().replace('_', ' ')}; design may proceed through normal design contracts and evidence gates."


def _is_ignored(relative: str) -> bool:
    if relative.startswith(f"{GOVERNANCE_ROOT}/"):
        return True
    parts = Path(relative).parts
    return any(part in IGNORED_DIRECTORIES for part in parts)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _stable_report(report: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in report.items() if key not in {"observedAt", "humanSummary", "reportSha256"}}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:80] or "finding"
