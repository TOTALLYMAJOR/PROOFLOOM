from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .assessment import assess_repository
from .context import build_context
from .contracts import create_contract
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


def contract_from_workflow(
    task: str,
    root: Path,
    assessment: dict[str, Any],
    context: dict[str, Any],
    surface: str | None,
) -> dict[str, Any]:
    model = context["actor_task_model"]
    return {
        "taskId": _slug(task),
        "product": context.get("profile", {}).get("name") or root.name,
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
    packet = {
        "adapter": adapter,
        "task": workflow["task"],
        "root": workflow["root"],
        "contract": contract,
        "repository_posture": workflow["repository"],
        "evidence_adapter": workflow["evidence_adapter"],
        "references": workflow["references"],
        "instructions": [
            "Inspect the repository authorities named in the contract before editing.",
            "Keep runtime and business behavior intact unless the task explicitly authorizes a behavior change.",
            "Use references as pattern research only; never copy their identity, and create an original composition for the actor, state, and decision in this contract.",
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
    return "\n".join(lines)


def render_handoff_markdown(packet: dict[str, Any]) -> str:
    contract = packet["contract"]
    lines = [
        f"# Design Implementation Handoff: {packet['task']}",
        "",
        f"Target repository: `{packet['root']}`",
        f"Primary action: {contract['primaryAction']}",
        "",
        "## Preserve",
    ]
    lines.extend(f"- {item}" for item in contract["preserve"] or ["Repository authority discovered during inspection."])
    lines.extend(["", "## Do not add or change"])
    lines.extend(f"- {item}" for item in contract["doNotTouch"])
    lines.extend(["", "## Instructions"])
    lines.extend(f"- {item}" for item in packet["instructions"])
    if packet["references"]["sources"]:
        lines.extend(["", "## References"])
        lines.extend(f"- Research {source}; transfer principles only, never copy its identity." for source in packet["references"]["sources"])
    lines.extend(["", "## Required proof"])
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
