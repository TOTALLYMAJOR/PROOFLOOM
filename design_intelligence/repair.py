from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import RepairRun
from .storage import atomic_write_text, ensure_within, sha256_file


FORBIDDEN_PARTS = {
    ".design/baselines",
    ".design/quality/thresholds.json",
    "playwright.config",
    "tests/",
    "migrations/",
    "backend/",
    "server/",
    "api/",
}
ALLOWED_SEVERITIES = {"P0", "P1", "P2"}


def apply_repair_plan(
    repository_root: str | Path,
    plan: dict[str, Any],
    evidence: dict[str, Any],
    iteration: int,
    apply: bool = False,
) -> RepairRun:
    root = Path(repository_root).resolve()
    max_iterations = int(plan.get("iterationLimit", 0))
    blocked: list[str] = []
    if plan.get("authority") != "visual-only":
        blocked.append("Authority boundary is not visual-only")
    if max_iterations < 1 or max_iterations > 3:
        blocked.append("Repair iteration limit must be between 1 and 3")
    if iteration < 1 or iteration > max_iterations or iteration > 3:
        blocked.append("Repair iteration exceeds the bounded limit")
    if plan.get("architectureImpact"):
        blocked.append("Architecture-impacting repairs require human implementation")
    allowed_files = set(plan.get("allowedFiles", []))
    evidence_ids = {item.get("id") for item in evidence.get("findings", [])}
    prepared: list[tuple[Path, dict[str, Any]]] = []
    updated_text: dict[Path, str] = {}
    before_hashes: dict[str, str] = {}
    for repair in plan.get("repairs", []):
        relative = str(repair.get("file", "")).replace("\\", "/")
        if relative not in allowed_files:
            blocked.append(f"File is outside allowedFiles: {relative}")
            continue
        if any(part in relative.lower() for part in FORBIDDEN_PARTS):
            blocked.append(f"Forbidden repair target: {relative}")
            continue
        if repair.get("severity") not in ALLOWED_SEVERITIES:
            blocked.append(f"Unsupported repair severity: {repair.get('severity')}")
            continue
        if repair.get("evidenceId") not in evidence_ids:
            blocked.append(f"Required evidence not found: {repair.get('evidenceId')}")
            continue
        try:
            path = ensure_within(root, relative)
        except ValueError as exc:
            blocked.append(str(exc))
            continue
        if not path.is_file():
            blocked.append(f"Repair target does not exist: {relative}")
            continue
        text = updated_text.get(path, path.read_text(encoding="utf-8"))
        expected = repair.get("expected", "")
        if not expected or text.count(expected) != 1:
            blocked.append(f"Expected text must match exactly once: {relative}")
            continue
        before_hashes.setdefault(relative, sha256_file(path))
        updated_text[path] = text.replace(expected, repair.get("replacement", ""), 1)
        prepared.append((path, repair))
    if blocked:
        return RepairRun(
            plan_id=plan.get("id", "unknown"),
            status="BLOCKED",
            iteration=iteration,
            max_iterations=max_iterations,
            changed_files=[],
            applied_repairs=[],
            blocked_reasons=blocked,
            before_hashes=before_hashes,
            after_hashes={},
        )
    changed_files: list[str] = []
    applied_repairs: list[dict[str, Any]] = []
    after_hashes: dict[str, str] = {}
    if apply:
        for path, updated in updated_text.items():
            atomic_write_text(path, updated)
            relative = path.relative_to(root).as_posix()
            changed_files.append(relative)
            after_hashes[relative] = sha256_file(path)
        for path, repair in prepared:
            relative = path.relative_to(root).as_posix()
            applied_repairs.append(
                {"findingId": repair["findingId"], "file": relative, "severity": repair["severity"]}
            )
    return RepairRun(
        plan_id=plan.get("id", "unknown"),
        status="APPLIED" if apply else "DRY_RUN",
        iteration=iteration,
        max_iterations=max_iterations,
        changed_files=changed_files,
        applied_repairs=applied_repairs,
        blocked_reasons=[],
        before_hashes=before_hashes,
        after_hashes=after_hashes,
    )
