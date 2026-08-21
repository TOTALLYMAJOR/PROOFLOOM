from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from .storage import atomic_write_json


REQUIRED_FIELDS = (
    "taskId",
    "product",
    "surface",
    "actor",
    "object",
    "goal",
    "decision",
    "state",
    "blocker",
    "authority",
    "primaryAction",
    "informationPriority",
    "preserve",
    "change",
    "reuse",
    "introduce",
    "doNotTouch",
    "responsiveRequirements",
    "accessibilityRequirements",
    "acceptanceCriteria",
    "relevantDesignDecisions",
)

LIST_FIELDS = (
    "preserve",
    "change",
    "reuse",
    "introduce",
    "doNotTouch",
    "responsiveRequirements",
    "accessibilityRequirements",
    "acceptanceCriteria",
    "relevantDesignDecisions",
)


def design_contract_schema() -> dict[str, Any]:
    path = files("design_intelligence").joinpath("data/schemas/design-contract.schema.json")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_contract(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in contract:
            errors.append(f"Missing required field: {field}")
    for field in REQUIRED_FIELDS[:11]:
        if field in contract and (not isinstance(contract[field], str) or not contract[field].strip()):
            errors.append(f"{field} must be a non-empty string")
    for field in LIST_FIELDS:
        if field in contract and not isinstance(contract[field], list):
            errors.append(f"{field} must be an array")
    priorities = contract.get("informationPriority")
    if priorities is not None:
        if not isinstance(priorities, dict):
            errors.append("informationPriority must be an object")
        else:
            for field in ("primary", "secondary", "supporting", "rare"):
                if not isinstance(priorities.get(field), list):
                    errors.append(f"informationPriority.{field} must be an array")
    if not contract.get("acceptanceCriteria"):
        errors.append("acceptanceCriteria must contain at least one measurable criterion")
    return errors


def create_contract(payload: dict[str, Any], output: str | Path | None = None) -> dict[str, Any]:
    priorities = payload.get("informationPriority") or {}
    contract = {
        "schemaVersion": 1,
        **{field: payload.get(field, "") for field in REQUIRED_FIELDS[:11]},
        "informationPriority": {
            field: list(priorities.get(field, []))
            for field in ("primary", "secondary", "supporting", "rare")
        },
        **{field: list(payload.get(field, [])) for field in LIST_FIELDS},
    }
    errors = validate_contract(contract)
    if errors:
        raise ValueError("Invalid design contract: " + "; ".join(errors))
    if output:
        atomic_write_json(output, contract)
    return contract


def load_and_validate_contract(path: str | Path) -> tuple[dict[str, Any], list[str]]:
    contract = json.loads(Path(path).read_text(encoding="utf-8"))
    return contract, validate_contract(contract)
