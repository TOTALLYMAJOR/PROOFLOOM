from __future__ import annotations

import re
import shlex
from typing import Any


SURFACE_MODES = ("marketing", "app-workflow", "customer-proposal", "mobile", "general")


MODE_GUIDANCE = {
    "marketing": {
        "label": "Marketing and conversion",
        "priorities": [
            "Make the product promise understandable within five seconds.",
            "Show credible product proof before feature breadth.",
            "Keep one dominant trial, demo, or exploration action.",
        ],
        "proof": ["hero comprehension", "CTA dominance", "product proof visibility", "mobile conversion path"],
    },
    "app-workflow": {
        "label": "Application workflow",
        "priorities": [
            "Make state, blocker, authority, and next action obvious.",
            "Keep decision-critical context attached to the working object.",
            "Use progressive disclosure for advanced and exceptional work.",
        ],
        "proof": ["task completion path", "state and action proximity", "keyboard operation", "responsive workflow continuity"],
    },
    "customer-proposal": {
        "label": "Customer proposal and decision",
        "priorities": [
            "Make the decision and its consequences easy to understand.",
            "Keep price, options, revisions, and acceptance authority explicit.",
            "Reduce anxiety without hiding commercial truth.",
        ],
        "proof": ["option comprehension", "price clarity", "acceptance consequence", "mobile decision path"],
    },
    "mobile": {
        "label": "Mobile-focused surface",
        "priorities": [
            "Optimize for glance, decision, and thumb-reachable action.",
            "Preserve essential state while deferring secondary detail.",
            "Avoid desktop layouts compressed into a narrow viewport.",
        ],
        "proof": ["390px primary action", "no horizontal overflow", "touch target clarity", "disclosure continuity"],
    },
    "general": {
        "label": "General product surface",
        "priorities": [
            "Preserve the product's established design authority.",
            "Make the dominant decision and next action unmistakable.",
            "Change only what the stated task requires.",
        ],
        "proof": ["hierarchy", "workflow clarity", "desktop and mobile rendering", "accessibility"],
    },
}


DIRECTION_TEMPLATES = {
    "marketing": [
        ("value-first-proof", "Value-first proof", "Lead with the commercial outcome, then prove it with the real product workflow."),
        ("workflow-story", "Workflow story", "Turn the product journey into a concise visual narrative from problem to completed outcome."),
        ("category-authority", "Category authority", "Use confident editorial hierarchy to frame the product as the modern standard for its category."),
    ],
    "app-workflow": [
        ("action-first-instrument", "Action-first instrument", "Organize the surface around current state, one dominant decision, and the next valid action."),
        ("context-workspace", "Context workspace", "Keep the working object central while placing history, guidance, and secondary controls in supporting regions."),
        ("progressive-command", "Progressive command surface", "Expose routine actions immediately and reveal advanced or exceptional controls only when relevant."),
    ],
    "customer-proposal": [
        ("decision-first-proposal", "Decision-first proposal", "Lead with the offer, options, total consequence, and a clear acceptance path."),
        ("guided-comparison", "Guided comparison", "Make tradeoffs visible and help the customer compare meaningful choices without table overload."),
        ("editorial-trust", "Editorial trust", "Use document-like pacing and restrained commercial polish to make the proposal feel considered and credible."),
    ],
    "mobile": [
        ("glance-and-act", "Glance and act", "Show what changed, what matters now, and the next thumb-reachable action."),
        ("stepwise-focus", "Stepwise focus", "Turn a dense workflow into short, stateful decisions with clear progress and recovery."),
        ("compact-ledger", "Compact decision ledger", "Prioritize status, consequences, and recent decisions while collapsing supporting detail."),
    ],
    "general": [
        ("preserve-and-focus", "Preserve and focus", "Keep the established visual language and strengthen hierarchy around the primary task."),
        ("workflow-first", "Workflow first", "Let the actor, object, state, blocker, and next action determine the composition."),
        ("product-expression", "Product expression", "Strengthen product-specific typography, rhythm, and interaction without changing runtime authority."),
    ],
}


def build_mission(
    workflow: dict[str, Any],
    references: list[str] | None = None,
    requested_mode: str | None = None,
    requested_direction: str | None = None,
) -> dict[str, Any]:
    mode = infer_surface_mode(workflow["task"], workflow.get("surface"), requested_mode)
    directions = build_direction_briefs(workflow, mode["id"])
    recommended = directions[0]["id"]
    selected = resolve_direction(requested_direction, directions, recommended)
    ledger = build_reference_ledger(references or [])
    proof = build_proof_gate(workflow, mode)
    approval_status = "APPROVED" if selected else "PENDING"
    status = "READY_TO_IMPLEMENT" if selected else "DIRECTION_REVIEW_REQUIRED"
    selection_command = _selection_command(workflow, recommended, mode, ledger)
    next_action = (
        f"Implement the approved '{selected['name']}' direction, then satisfy the rendered-proof gate."
        if selected
        else f"Review the three directions. To accept the recommendation, run: {selection_command}"
    )
    return {
        "schemaVersion": 1,
        "status": status,
        "taskId": workflow["task_id"],
        "task": workflow["task"],
        "root": workflow["root"],
        "surface": workflow["surface"],
        "profile": workflow["profile"],
        "mode": mode,
        "directions": directions,
        "recommendedDirection": recommended,
        "selectedDirection": selected["id"] if selected else None,
        "directionApproval": {
            "required": True,
            "status": approval_status,
            "rule": "A recommendation is not approval. Implementation starts only after an explicit direction selection.",
        },
        "referenceLedger": ledger,
        "proofGate": proof,
        "selectionCommand": selection_command,
        "nextAction": next_action,
    }


def infer_surface_mode(task: str, surface: str | None, requested_mode: str | None = None) -> dict[str, Any]:
    if requested_mode:
        if requested_mode not in SURFACE_MODES:
            raise ValueError(f"Unknown surface mode '{requested_mode}'. Choose from: {', '.join(SURFACE_MODES)}")
        return _mode_payload(requested_mode, False, "Selected explicitly by the user.")

    text = f"{task} {surface or ''}".lower()
    rules = [
        ("mobile", r"\b(mobile|phone|small[- ]screen|responsive)\b"),
        ("marketing", r"\b(landing|homepage|home page|marketing|hero|pricing|conversion|trial|demo|website)\b"),
        ("customer-proposal", r"\b(customer proposal|client proposal|proposal review|acceptance|approve quote|customer quote|payment decision)\b"),
        ("app-workflow", r"\b(workspace|dashboard|builder|admin|operations|workflow|form|wizard|create|edit|configure)\b"),
    ]
    for mode, pattern in rules:
        if re.search(pattern, text):
            return _mode_payload(mode, True, f"Inferred from task or surface language matching {MODE_GUIDANCE[mode]['label'].lower()} work.")
    return _mode_payload("general", True, "No specialized surface signal was strong enough, so repository-specific general guidance applies.")


def build_direction_briefs(workflow: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    contract = workflow["contract"]
    result = []
    for index, (identifier, name, thesis) in enumerate(DIRECTION_TEMPLATES[mode]):
        result.append({
            "id": identifier,
            "name": name,
            "recommended": index == 0,
            "thesis": thesis,
            "productFit": [
                f"Supports the goal: {contract['goal']}",
                f"Keeps the primary action dominant: {contract['primaryAction']}",
                f"Preserves repository authority while changing only: {workflow['task']}",
            ],
            "referenceRoles": _reference_roles(mode, index),
            "risks": _direction_risks(mode, index),
        })
    return result


def resolve_direction(
    requested: str | None,
    directions: list[dict[str, Any]],
    recommended: str,
) -> dict[str, Any] | None:
    if not requested:
        return None
    selected_id = recommended if requested == "recommended" else requested
    for direction in directions:
        if direction["id"] == selected_id:
            return direction
    valid = ", ".join(direction["id"] for direction in directions)
    raise ValueError(f"Unknown direction '{requested}'. Choose one of: recommended, {valid}")


def build_reference_ledger(references: list[str]) -> dict[str, Any]:
    entries = []
    for index, source in enumerate(references, start=1):
        entries.append({
            "id": f"REF-{index:03d}",
            "source": source,
            "status": "RESEARCH_REQUIRED",
            "role": "unassigned",
            "observedPatterns": [],
            "whyItWorks": [],
            "productRelevance": [],
            "originalTransformation": [],
            "reject": [],
        })
    return {
        "status": "RESEARCH_REQUIRED" if entries else "NOT_REQUIRED",
        "entries": entries,
        "rule": "A URL or DESIGN.md is research input, not analyzed evidence. Complete the ledger before importing a reference pattern.",
        "authority": "Repository and product truth outrank every ledger entry.",
    }


def build_proof_gate(workflow: dict[str, Any], mode: dict[str, Any]) -> dict[str, Any]:
    evidence = workflow["evidence_adapter"]
    has_evidence = bool(evidence["qa_reports"] or evidence["review_manifests"] or evidence["screenshots"])
    return {
        "required": True,
        "status": "EVIDENCE_FOUND" if has_evidence else "PENDING",
        "browserTools": evidence["browser_tools"],
        "checks": [
            *mode["proof"],
            "deterministic design lint",
            "critical and serious accessibility findings",
            "desktop and mobile rendered evidence",
        ],
        "commands": evidence["recommended_commands"],
        "rule": "Use the repository's existing browser and test hierarchy. Do not create a parallel E2E system.",
    }


def render_mission_text(mission: dict[str, Any]) -> str:
    mode = mission["mode"]
    lines = [
        "DESIGN MISSION",
        "",
        f"Status: {mission['status']}",
        f"Task: {mission['task']}",
        f"Mode: {mode['label']} ({'inferred' if mode['inferred'] else 'selected'})",
        f"Surface: {mission['surface']}",
        "",
        "Directions:",
    ]
    for direction in mission["directions"]:
        suffix = " [recommended]" if direction["recommended"] else ""
        selected = " [selected]" if direction["id"] == mission["selectedDirection"] else ""
        lines.append(f"- {direction['id']}: {direction['name']}{suffix}{selected}")
        lines.append(f"  {direction['thesis']}")
    lines.extend([
        "",
        f"Reference ledger: {mission['referenceLedger']['status']}",
        f"Rendered proof: {mission['proofGate']['status']}",
        "",
        "Next action:",
        mission["nextAction"],
    ])
    return "\n".join(lines)


def _mode_payload(mode: str, inferred: bool, rationale: str) -> dict[str, Any]:
    guidance = MODE_GUIDANCE[mode]
    return {
        "id": mode,
        "label": guidance["label"],
        "inferred": inferred,
        "rationale": rationale,
        "priorities": list(guidance["priorities"]),
        "proof": list(guidance["proof"]),
    }


def _selection_command(
    workflow: dict[str, Any],
    recommended: str,
    mode: dict[str, Any],
    ledger: dict[str, Any],
) -> str:
    parts = [
        "design-intelligence",
        shlex.quote(workflow["task"]),
        "--root",
        shlex.quote(workflow["root"]),
        "--mode",
        mode["id"],
        "--direction",
        recommended,
        "--save",
    ]
    if workflow.get("profile_key"):
        parts.extend(["--profile", workflow["profile_key"]])
    for entry in ledger["entries"]:
        parts.extend(["--reference", shlex.quote(entry["source"])])
    return " ".join(parts)


def _reference_roles(mode: str, index: int) -> list[str]:
    roles = {
        "marketing": ["conversion storytelling", "workflow proof", "typography and category confidence"],
        "app-workflow": ["interaction hierarchy", "workspace architecture", "progressive disclosure"],
        "customer-proposal": ["decision clarity", "comparison behavior", "editorial trust"],
        "mobile": ["mobile action hierarchy", "step progression", "compact state communication"],
        "general": ["surface hierarchy", "workflow clarity", "product-specific expression"],
    }
    primary = roles[mode][index]
    return [primary, "responsive behavior", "accessibility behavior"]


def _direction_risks(mode: str, index: int) -> list[str]:
    common = ["Do not replace established tokens or primitives without repository evidence."]
    if index == 0:
        return [*common, "Focus can become sparse if supporting context is removed instead of progressively disclosed."]
    if index == 1:
        return [*common, "Narrative or workspace structure can become overbuilt if every step receives equal visual weight."]
    return [*common, "Expressive styling can overpower task clarity or drift toward a generic SaaS identity."]
