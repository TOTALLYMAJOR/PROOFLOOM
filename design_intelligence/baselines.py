from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .memory import memory_root
from .storage import atomic_write_json, read_json, read_jsonl, sha256_file


def promote_baseline(
    repository_root: str | Path,
    scenario_id: str,
    current_root: str | Path,
    approval_path: str | Path,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    current = Path(current_root).resolve()
    approval = read_json(approval_path, {}) or {}
    errors = _validate_approval(root, approval)
    if errors:
        raise ValueError("Baseline promotion denied: " + "; ".join(errors))
    images = sorted(current.glob("*/current.png"))
    if not images:
        raise ValueError(f"No current screenshots found below {current}")
    baseline_root = root / ".design/baselines" / scenario_id
    manifest_path = root / ".design/baselines/manifest.json"
    manifest = read_json(manifest_path, {"schemaVersion": 1, "scenarios": {}}) or {"schemaVersion": 1, "scenarios": {}}
    entries: dict[str, Any] = {}
    for image in images:
        viewport = image.parent.name
        destination = baseline_root / viewport / "baseline.png"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(image, destination)
        entries[viewport] = {
            "path": destination.relative_to(root).as_posix(),
            "sha256": sha256_file(destination),
        }
    manifest.setdefault("scenarios", {})[scenario_id] = {
        "approvedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "approval": approval,
        "viewports": entries,
    }
    atomic_write_json(manifest_path, manifest)
    return manifest["scenarios"][scenario_id]


def audit_baselines(repository_root: str | Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    manifest = read_json(root / ".design/baselines/manifest.json", {}) or {}
    errors: list[str] = []
    checked = 0
    for scenario_id, scenario in manifest.get("scenarios", {}).items():
        approval_errors = _validate_approval(root, scenario.get("approval", {}))
        errors.extend(f"{scenario_id}: {error}" for error in approval_errors)
        for viewport, entry in scenario.get("viewports", {}).items():
            path = root / entry.get("path", "")
            checked += 1
            if not path.is_file():
                errors.append(f"{scenario_id}/{viewport}: baseline missing")
            elif sha256_file(path) != entry.get("sha256"):
                errors.append(f"{scenario_id}/{viewport}: baseline hash mismatch")
    return {"status": "PASS" if not errors else "FAIL", "checked": checked, "errors": errors}


def _validate_approval(repository_root: Path, approval: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = ("decisionId", "reason", "authorizedBy", "validationStatus", "validationEvidence")
    for field in required:
        if not approval.get(field):
            errors.append(f"approval.{field} is required")
    if approval.get("validationStatus") != "PASS":
        errors.append("approval.validationStatus must be PASS")
    authority = str(approval.get("authorizedBy", "")).lower()
    if not authority or authority.startswith("agent") or authority == "quality-gate":
        errors.append("baseline promotion requires explicit human authority")
    decisions = read_jsonl(memory_root(repository_root) / "decisions.jsonl")
    accepted = [item for item in decisions if item.get("id") == approval.get("decisionId") and item.get("status") == "accepted"]
    if not accepted:
        errors.append(f"accepted decision not found: {approval.get('decisionId')}")
    return errors
