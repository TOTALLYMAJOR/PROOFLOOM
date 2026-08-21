from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .repository import select_candidate_files
from .storage import atomic_write_json, read_json, sha256_file


COMPONENT_SUFFIXES = {".tsx", ".jsx", ".vue", ".svelte"}
COMPONENT_DIR_RE = re.compile(r"(?:^|/)(?:components|ui|shared-ui|design-system|src/components)/")


def build_component_registry(repository_root: str | Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    components: list[dict[str, Any]] = []
    for path in select_candidate_files(root):
        relative = path.relative_to(root).as_posix()
        if relative.startswith("tests/fixtures/"):
            continue
        if path.suffix.lower() not in COMPONENT_SUFFIXES or not COMPONENT_DIR_RE.search(relative):
            continue
        components.append(
            {
                "id": f"component:{relative}",
                "name": path.stem,
                "path": relative,
                "sha256": sha256_file(path),
                "status": "active",
                "authority": "repository-source",
                "lastValidatedAt": None,
                "designDecisionIds": [],
                "surfaces": [],
                "debtIds": [],
            }
        )
    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": "deterministic-repository-scan",
        "components": sorted(components, key=lambda item: item["path"]),
    }


def write_component_registry(repository_root: str | Path, output: str | Path | None = None) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    destination = Path(output) if output else root / ".design/memory/component-registry.json"
    if not destination.is_absolute():
        destination = root / destination
    registry = build_component_registry(root)
    existing = read_json(destination, {}) or {}
    metadata = {item.get("path"): item for item in existing.get("components", [])}
    for component in registry["components"]:
        prior = metadata.get(component["path"], {})
        for key in ("lastValidatedAt", "designDecisionIds", "surfaces", "debtIds"):
            if prior.get(key):
                component[key] = prior[key]
    atomic_write_json(destination, registry)
    return registry


def audit_component_registry(repository_root: str | Path, as_of: date | None = None, stale_days: int = 90) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    registry_path = root / ".design/memory/component-registry.json"
    registry = read_json(registry_path, {}) or {}
    stale: list[dict[str, Any]] = []
    missing: list[str] = []
    drifted: list[str] = []
    today = as_of or date.today()
    for component in registry.get("components", []):
        path = root / component.get("path", "")
        if not path.is_file():
            missing.append(component.get("path", ""))
            continue
        if component.get("sha256") and sha256_file(path) != component["sha256"]:
            drifted.append(component["path"])
        validated = component.get("lastValidatedAt")
        if validated:
            try:
                age = (today - date.fromisoformat(validated[:10])).days
                if age > stale_days:
                    stale.append({"id": component.get("id"), "path": component["path"], "ageDays": age})
            except ValueError:
                stale.append({"id": component.get("id"), "path": component["path"], "ageDays": None})
    status = "PASS" if not missing and not drifted else "FAIL"
    return {
        "status": status,
        "components": len(registry.get("components", [])),
        "missing": missing,
        "drifted": drifted,
        "stale": stale,
    }
