from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .assessment import assess_repository
from .context import build_context
from .contracts import create_contract
from .missions import build_mission, render_mission_text
from .repository import inspect_repository


def build_workflow(
    root: str,
    task: str,
    profile_name: str | None = None,
    surface: str | None = None,
    brief: dict[str, Any] | None = None,
    references: list[str] | None = None,
) -> dict[str, Any]:
    """Build a read-only, repository-specific design work plan."""
    target = Path(root).resolve()
    task_brief = {**(brief or {})}
    task_brief.setdefault("goal", task)
    if surface:
        task_brief.setdefault("object", surface)

    assessment = assess_repository(str(target))
    context = build_context(str(target), profile_name, task_brief)
    artifacts = discover_evidence(target, task)
    return {
        "status": "READY",
        "task": task,
        "task_id": _slug(task),
        "root": str(target),
        "surface": surface or context.actor_task_model.object,
        "profile": context.profile.name if context.profile else None,
        "profile_key": profile_name,
        "contract": contract_from_workflow(task, target, assessment.to_dict(), context.to_dict(), surface),
        "repository": {
            "recommendation": assessment.recommendation.value,
            "structure_risk": assessment.structure_risk.value,
            "preserve": assessment.preserve,
            "integrate": assessment.integrate,
            "do_not_add": assessment.do_not_add,
        },
        "workflow": [
            {
                "step": "understand",
                "action": "Use the actor-task model and repository authorities before changing the interface.",
                "required": True,
            },
            {
                "step": "implement",
                "action": "Reuse the existing tokens and components; keep business behavior unchanged unless the task explicitly changes it.",
                "required": True,
            },
            {
                "step": "verify",
                "action": "Run deterministic lint plus the consuming repository's existing browser tooling at desktop and mobile widths.",
                "required": True,
            },
            {
                "step": "record",
                "action": "Create an evidence pack only after validation evidence exists.",
                "required": True,
            },
        ],
        "evidence_adapter": artifacts,
        "best_practices": _best_practices(context.to_dict(), artifacts),
        "style_sources": discover_style_sources(target, references, profile_name),
        "references": {
            "sources": references or [],
            "rule": "Research each source for transferable patterns, then transform them for this product. Do not copy branding, layouts, assets, or copy.",
        },
        "next_action": "Review the generated contract, then give it to the implementation agent with the handoff command.",
    }


def discover_evidence(root: str | Path, task: str | None = None) -> dict[str, Any]:
    """Locate existing evidence without creating a competing browser hierarchy."""
    target = Path(root).resolve()
    snapshot = inspect_repository(str(target))
    artifacts_root = target / "artifacts"
    candidates = _artifact_candidates(artifacts_root, task)
    browser_tools = []
    if snapshot.playwright.status.value != "NONE":
        browser_tools.append("Playwright")
    if snapshot.cypress.status.value != "NONE":
        browser_tools.append("Cypress")
    if snapshot.storybook.status.value != "NONE":
        browser_tools.append("Storybook")
    if not browser_tools:
        browser_tools.append("No existing browser tool detected")

    recommended = ["design-intelligence lint --root <repo>"]
    if candidates["review_manifests"]:
        recommended.append(
            "design-intelligence validate --root <repo> --review-input "
            + candidates["review_manifests"][0]
            + " --evidence-pack-out artifacts/design/evidence/<task>/evidence-pack.md"
        )
    else:
        recommended.append("Run the existing browser tool, then supply its review manifest to design-intelligence validate.")
    return {
        "read_only": True,
        "browser_tools": browser_tools,
        "artifact_root": _relative(target, artifacts_root) if artifacts_root.exists() else None,
        "review_manifests": candidates["review_manifests"],
        "qa_reports": candidates["qa_reports"],
        "screenshots": candidates["screenshots"],
        "recommended_commands": recommended,
        "note": "Existing test and artifact conventions remain canonical; this adapter only discovers them.",
    }


def discover_style_sources(
    root: str | Path,
    references: list[str] | None = None,
    profile_name: str | None = None,
) -> dict[str, Any]:
    """Describe where style guidance should come from before external inspiration dominates."""
    target = Path(root).resolve()
    snapshot = inspect_repository(str(target))
    repo_sources = []
    repo_sources.extend(snapshot.capability_map.get("design_language").authorities)
    repo_sources.extend(snapshot.design_documentation.evidence)
    repo_sources.extend(snapshot.design_tokens.evidence)
    repo_sources.extend(snapshot.typography.evidence)
    repo_sources.extend(snapshot.agent_governance.evidence)
    repo_sources.extend(snapshot.playwright.evidence[:1])
    repo_sources.extend(snapshot.storybook.evidence[:1])
    repository_sources = sorted(set(repo_sources))

    reference_sources = list(references or [])
    transformed = None
    if reference_sources:
        transformed = {
            "status": "RESEARCH_REQUIRED",
            "sources": reference_sources,
            "note": "Source names and URLs are not analyzed evidence. Record observed patterns and original transformations before use.",
        }
    return {
        "repository": {
            "styling": snapshot.styling,
            "component_system": snapshot.component_system,
            "sources": repository_sources,
            "priority": "Repository style authority beats admired references.",
        },
        "references": transformed,
        "research_order": [
            "Inspect the repository's existing design language, tokens, typography, and component primitives first.",
            "Look at the repository's current browser or story evidence before introducing a new style direction.",
            "Use admired repos or external references to extract transferable patterns only after repository truth is clear.",
            "Transform observed patterns into an original composition tied to the actor, state, and dominant decision.",
        ],
    }


def contract_from_workflow(
    task: str,
    root: Path,
    assessment: dict[str, Any],
    context: dict[str, Any],
    surface: str | None,
) -> dict[str, Any]:
    model = context["actor_task_model"]
    profile = context.get("profile") or {}
    return {
        "taskId": _slug(task),
        "product": profile.get("name") or root.name,
        "surface": surface or model["object"],
        "actor": model["actor"],
        "object": model["object"],
        "goal": model["goal"],
        "decision": model["decision"],
        "state": model["state"],
        "blocker": model["blocker"],
        "authority": model["authority"],
        "primaryAction": model["next_action"],
        "informationPriority": {
            "primary": [model["decision"], model["next_action"]],
            "secondary": [model["state"], model["blocker"]],
            "supporting": list(context["design_language_focus"]),
            "rare": ["Structural migration only when the repository assessment justifies it."],
        },
        "preserve": assessment["preserve"],
        "change": [task],
        "reuse": assessment["integrate"],
        "introduce": [],
        "doNotTouch": assessment["do_not_add"],
        "responsiveRequirements": list(context["validation_focus"]),
        "accessibilityRequirements": ["Keep controls named and keyboard-operable.", "Validate the rendered desktop and mobile surface."],
        "acceptanceCriteria": ["The primary next action is visible without competing with secondary information.", *context["validation_focus"]],
        "relevantDesignDecisions": [],
    }


def write_contract_from_workflow(workflow: dict[str, Any], output: str | Path) -> dict[str, Any]:
    return create_contract(workflow["contract"], output)


def build_handoff(workflow: dict[str, Any], adapter: str) -> dict[str, Any]:
    contract = workflow["contract"]
    mission = workflow.get("mission")
    selected_direction = None
    if mission and mission["selectedDirection"]:
        selected_direction = next(
            direction for direction in mission["directions"]
            if direction["id"] == mission["selectedDirection"]
        )
    direction_instructions = []
    if selected_direction:
        direction_instructions.append(
            f"Implement the explicitly selected direction: {selected_direction['name']} - {selected_direction['thesis']}"
        )
    elif mission:
        direction_instructions.append(
            "Do not edit implementation yet. Present the three direction briefs and obtain an explicit direction selection."
        )
    packet = {
        "adapter": adapter,
        "task": workflow["task"],
        "root": workflow["root"],
        "contract": contract,
        "repository_posture": workflow["repository"],
        "evidence_adapter": workflow["evidence_adapter"],
        "best_practices": workflow["best_practices"],
        "style_sources": workflow["style_sources"],
        "references": workflow["references"],
        "mission": mission,
        "instructions": [
            *direction_instructions,
            "Inspect the repository authorities named in the contract before editing.",
            "Keep runtime and business behavior intact unless the task explicitly authorizes a behavior change.",
            "Use references as pattern research only; never copy their identity, and create an original composition for the actor, state, and decision in this contract.",
            "Understand established UX and design best practices before styling: make the dominant action obvious, keep state with action, and use progressive disclosure instead of equal visual weight.",
            "Use the repository itself to find the style baseline before borrowing from admired repos or external references.",
            "Validate desktop and mobile with the repository's existing browser tooling, then run design-intelligence lint and validate.",
            "Do not weaken tests, baselines, thresholds, or accessibility checks to make the work pass.",
        ],
        "stop_conditions": [
            "A required repository authority conflicts with the proposed change.",
            "The task requires runtime restructuring not justified by the repository assessment.",
            "Evidence shows a P0 or P1 accessibility, overflow, off-screen, or workflow defect.",
        ],
    }
    packet["prompt"] = render_handoff_markdown(packet)
    return packet


def render_workflow_text(workflow: dict[str, Any]) -> str:
    lines = ["DESIGN WORK", "", f"Task: {workflow['task']}", f"Profile: {workflow['profile'] or 'none'}", f"Surface: {workflow['surface']}", "", "Next action:", workflow["next_action"], "", "Repository posture:"]
    lines.extend(f"- {item}" for item in workflow["repository"]["preserve"] or ["No existing authority detected."])
    lines.extend(["", "Workflow:"])
    lines.extend(f"- {item['step']}: {item['action']}" for item in workflow["workflow"])
    lines.extend(["", "Evidence adapter:"])
    lines.extend(f"- {item}" for item in workflow["evidence_adapter"]["recommended_commands"])
    lines.extend(["", "Style sources:"])
    lines.extend(f"- {item}" for item in workflow["style_sources"]["research_order"])
    return "\n".join(lines)


def render_handoff_markdown(packet: dict[str, Any]) -> str:
    contract = packet["contract"]
    mission = packet.get("mission")
    lines = [
        f"# Design Mission Handoff: {packet['task']}",
        "",
        f"Target repository: `{packet['root']}`",
        f"Primary action: {contract['primaryAction']}",
    ]
    if mission:
        lines.extend([
            f"Mission status: `{mission['status']}`",
            f"Surface mode: `{mission['mode']['id']}`",
            "",
            "## Direction decision",
        ])
        for direction in mission["directions"]:
            labels = []
            if direction["recommended"]:
                labels.append("recommended")
            if direction["id"] == mission["selectedDirection"]:
                labels.append("selected")
            suffix = f" ({', '.join(labels)})" if labels else ""
            lines.extend([
                f"### {direction['name']}{suffix}",
                "",
                direction["thesis"],
                "",
                f"Direction ID: `{direction['id']}`",
                "",
            ])
        if not mission["selectedDirection"]:
            lines.extend([
                "Implementation is blocked until a direction is explicitly selected.",
                "",
                f"Recommended selection command: `{mission['selectionCommand']}`",
                "",
            ])
    lines.extend(["## Preserve"])
    lines.extend(f"- {item}" for item in contract["preserve"] or ["Repository authority discovered during inspection."])
    lines.extend(["", "## Do not add or change"])
    lines.extend(f"- {item}" for item in contract["doNotTouch"])
    lines.extend(["", "## Instructions"])
    lines.extend(f"- {item}" for item in packet["instructions"])
    lines.extend(["", "## Best practices"])
    lines.extend(f"- {item}" for item in packet["best_practices"])
    lines.extend(["", "## Style research order"])
    lines.extend(f"- {item}" for item in packet["style_sources"]["research_order"])
    lines.extend(["", "## Repository style authorities"])
    lines.extend(
        f"- {item}"
        for item in packet["style_sources"]["repository"]["sources"]
        or ["No explicit style authority was detected; inspect existing UI files before inventing a new visual language."]
    )
    if packet["references"]["sources"]:
        lines.extend(["", "## Reference ledger"])
        if mission:
            lines.append(f"Ledger status: `{mission['referenceLedger']['status']}`")
        lines.extend(f"- Research {source}; transfer principles only, never copy its identity." for source in packet["references"]["sources"])
    if mission:
        lines.extend(["", "## Required proof checks"])
        lines.extend(f"- {item}" for item in mission["proofGate"]["checks"])
    lines.extend(["", "## Required proof commands"])
    lines.extend(f"- {item}" for item in packet["evidence_adapter"]["recommended_commands"])
    lines.extend(["", "## Stop conditions"])
    lines.extend(f"- {item}" for item in packet["stop_conditions"])
    return "\n".join(lines)


def write_handoff(packet: dict[str, Any], output: str | Path) -> None:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
        return
    path.write_text(packet["prompt"], encoding="utf-8")


def build_start_packet(
    root: str,
    task: str,
    profile_name: str | None = None,
    surface: str | None = None,
    brief: dict[str, Any] | None = None,
    references: list[str] | None = None,
    adapter: str = "codex",
    mode: str | None = None,
    direction: str | None = None,
) -> dict[str, Any]:
    workflow = build_workflow(root, task, profile_name, surface, brief, references)
    if not surface:
        workflow["surface"] = task
        workflow["contract"]["surface"] = task
    mission = build_mission(workflow, references, mode, direction)
    workflow["mission"] = mission
    workflow["next_action"] = mission["nextAction"]
    handoff = build_handoff(workflow, adapter)
    return {
        "status": mission["status"],
        "task": task,
        "root": workflow["root"],
        "profile": workflow["profile"],
        "surface": workflow["surface"],
        "workflow": workflow,
        "mission": mission,
        "handoff": handoff,
        "quickstart": f"design-intelligence \"{task}\" --root {workflow['root']}",
        "prompt": handoff["prompt"],
        "summary": render_mission_text(mission),
        "next_action": mission["nextAction"],
    }


def save_start_packet(packet: dict[str, Any], output_root: str | Path | None = None) -> dict[str, str]:
    """Write a predictable, explicitly requested mission bundle."""
    repository_root = Path(packet["root"])
    base = Path(output_root) if output_root else repository_root / "artifacts" / "design" / "missions" / packet["mission"]["taskId"]
    base = base.resolve()
    base.mkdir(parents=True, exist_ok=True)

    mission_path = base / "mission.json"
    ledger_path = base / "reference-ledger.json"
    handoff_path = base / "handoff.md"
    mission_path.write_text(json.dumps(packet["mission"], indent=2) + "\n", encoding="utf-8")
    ledger_path.write_text(json.dumps(packet["mission"]["referenceLedger"], indent=2) + "\n", encoding="utf-8")
    handoff_path.write_text(packet["prompt"] + "\n", encoding="utf-8")

    outputs = {
        "directory": str(base),
        "mission": str(mission_path),
        "referenceLedger": str(ledger_path),
        "handoff": str(handoff_path),
    }
    if packet["mission"]["selectedDirection"]:
        contract_path = base / "design-contract.json"
        create_contract(packet["workflow"]["contract"], contract_path)
        outputs["contract"] = str(contract_path)
    return outputs


def _artifact_candidates(artifacts_root: Path, task: str | None) -> dict[str, list[str]]:
    buckets = {"review_manifests": [], "qa_reports": [], "screenshots": []}
    if not artifacts_root.is_dir():
        return buckets
    task_tokens = set(_slug(task or "").split("-")) - {"design", "work", "the", "a", "an"}
    for path in sorted(artifacts_root.rglob("*")):
        if not path.is_file() or len(sum(buckets.values(), [])) >= 60:
            continue
        relative = str(path.relative_to(artifacts_root.parent))
        if task_tokens and not task_tokens.intersection(_slug(relative).split("-")):
            continue
        if path.name == "review-manifest.json":
            buckets["review_manifests"].append(relative)
        elif path.name == "qa-report.json":
            buckets["qa_reports"].append(relative)
        elif path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            buckets["screenshots"].append(relative)
    return buckets


def _relative(root: Path, path: Path) -> str:
    return str(path.relative_to(root))


def _slug(value: str) -> str:
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", value.lower())) or "design-work"


def _best_practices(context: dict[str, Any], artifacts: dict[str, Any]) -> list[str]:
    practices = [
        "Solve actor, object, goal, decision, state, blocker, authority, and next action before visual polish.",
        "Make one dominant action obvious and keep secondary capability discoverable without equal visual weight.",
        "Keep status close to the action it informs; do not separate decision-critical information into decorative areas.",
        "Use progressive disclosure based on role, state, urgency, and device rather than hiding complexity arbitrarily.",
        "Validate the result at desktop and mobile widths with the repository's existing browser tooling when available.",
    ]
    practices.extend(context.get("reference_use", []))
    if artifacts["browser_tools"] and artifacts["browser_tools"][0] != "No existing browser tool detected":
        practices.append("Prefer the repository's existing validation and artifact conventions instead of creating a parallel review flow.")
    return practices
