from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .adoption import save_adoption_bundle
from .control_plane import (
    analyze_impact,
    architecture_graph,
    architecture_impact,
    audit_design_adoption,
    audit_visual_evidence,
    control_plane_health,
    create_task,
    discover_control_plane,
    evaluate_design_adoption,
    initialize_control_plane,
    inspect_design,
    program_status,
    run_control_plane_doctor,
    route_task_by_id,
    task_context,
    validate_control_plane,
    visual_plan,
)
from .planes import audit_backlog, audit_planes
from .governance import (
    apply_governance_convergence,
    audit_governance,
    plan_governance_convergence,
    verify_governance_convergence,
)
from .storage import atomic_write_json, ensure_within


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return _dispatch(args)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        payload = {"status": "FAIL", "command": _command_name(args), "errors": [str(error)]}
        _emit(payload, args, title="DEVCTL ERROR")
        return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devctl",
        description="Repository-native development control-plane facade.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = _common(subparsers.add_parser("init", help="Add the minimal control-plane manifest and task store."))
    init.add_argument("--dry-run", action="store_true", help="Discover and report proposed bindings without writing files.")
    _common(subparsers.add_parser("discover", help="Inspect repository authorities and readiness gaps without writes."))
    _common(subparsers.add_parser("validate", help="Validate devctl.yaml and declared authorities."))
    _common(subparsers.add_parser("doctor", help="Audit control-plane and delegated design authorities."))
    _common(subparsers.add_parser("health", help="Report intent, journey, backlog, standards, and routing health."))

    program = subparsers.add_parser(
        "program",
        help="Join governance, journeys, architecture, design, backlog, and evidence into one finalization program.",
    )
    program_subparsers = program.add_subparsers(dest="program_command", required=True)
    _common(program_subparsers.add_parser("status", help="Explain the current whole-program state."))
    _common(program_subparsers.add_parser("plan", help="Show the authority-safe whole-backlog program."))
    _common(program_subparsers.add_parser("complete", help="Fail unless every governed item and control gate is complete."))

    govern = subparsers.add_parser(
        "govern",
        help="Map, converge, apply, and verify repository understanding before design.",
    )
    govern_subparsers = govern.add_subparsers(dest="govern_command", required=True)
    _common(govern_subparsers.add_parser("audit", help="Map governing sources, journeys, conflicts, and damage."))
    _common(govern_subparsers.add_parser("plan", help="Build bounded automatic and authority-gated repair actions."))
    govern_apply = _common(govern_subparsers.add_parser("apply", help="Write derived bindings and drift protection without changing canonical authority."))
    govern_apply.add_argument(
        "--ratification",
        help="Owner-approved authority-drift ratification JSON required when rebasing changed critical authority.",
    )
    _common(govern_subparsers.add_parser("verify", help="Verify convergence, authority drift, and the pre-design gate."))

    planes = subparsers.add_parser("planes", help="Audit intent, architecture, and intelligence planes.")
    planes_subparsers = planes.add_subparsers(dest="planes_command", required=True)
    _common(planes_subparsers.add_parser("audit"))

    backlog = subparsers.add_parser("backlog", help="Inventory the entire declared backlog and dependency plan.")
    backlog_subparsers = backlog.add_subparsers(dest="backlog_command", required=True)
    _common(backlog_subparsers.add_parser("status"))
    _common(backlog_subparsers.add_parser("plan"))
    _common(backlog_subparsers.add_parser("complete"))

    intelligence = subparsers.add_parser("intelligence", help="Route tasks to vendor-neutral capability classes.")
    intelligence_subparsers = intelligence.add_subparsers(dest="intelligence_command", required=True)
    route = _common(intelligence_subparsers.add_parser("route"))
    route.add_argument("task_id")

    architecture = subparsers.add_parser(
        "architecture",
        help="Build and traverse the bounded repository architecture graph.",
    )
    architecture_subparsers = architecture.add_subparsers(dest="architecture_command", required=True)
    architecture_graph_parser = _common(
        architecture_subparsers.add_parser("graph", help="Build the deterministic static graph.")
    )
    architecture_graph_parser.add_argument(
        "--summary",
        action="store_true",
        help="Emit graph counts and digest without the node and edge payload.",
    )
    architecture_impact_parser = _common(
        architecture_subparsers.add_parser("impact", help="Trace task-scoped downstream impact.")
    )
    architecture_impact_parser.add_argument("task_id")
    architecture_impact_parser.add_argument("--changed", action="append", default=[])

    task = subparsers.add_parser("task", help="Create or retrieve bounded task packets.")
    task_subparsers = task.add_subparsers(dest="task_command", required=True)
    task_create = _common(task_subparsers.add_parser("create"))
    task_create.add_argument("--input", required=True, help="Task packet JSON file.")
    task_context_parser = _common(task_subparsers.add_parser("context"))
    task_context_parser.add_argument("task_id")
    task_context_parser.add_argument("--max-files", type=int)

    impact = _common(subparsers.add_parser("impact", help="Select affected verification from a task and paths."))
    impact.add_argument("task_id")
    impact.add_argument("--changed", action="append", default=[])

    verify = subparsers.add_parser("verify", help="Plan verification without executing arbitrary commands.")
    verify_subparsers = verify.add_subparsers(dest="verify_command", required=True)
    affected = _common(verify_subparsers.add_parser("affected"))
    affected.add_argument("task_id")
    affected.add_argument("--changed", action="append", default=[])

    design = subparsers.add_parser("design", help="Delegate to the existing Design Intelligence engine.")
    design_subparsers = design.add_subparsers(dest="design_command", required=True)
    _common(design_subparsers.add_parser("inspect"))
    adoption_audit = _common(design_subparsers.add_parser("adoption-audit"))
    adoption_audit.add_argument("--input", required=True)
    adopt = _common(design_subparsers.add_parser("adopt"))
    adopt.add_argument("task")
    adopt.add_argument("--reference", action="append", default=[])
    adopt.add_argument("--image", action="append", default=[])
    adopt.add_argument("--analysis")
    adopt.add_argument("--profile")
    adopt.add_argument("--surface")
    adopt.add_argument("--governance-receipt", action="append", default=[])
    adopt.add_argument("--save-to")
    adopt.add_argument("--strict", action="store_true")

    visual = subparsers.add_parser("visual", help="Plan or audit existing governed Playwright evidence.")
    visual_subparsers = visual.add_subparsers(dest="visual_command", required=True)
    visual_plan_parser = _common(visual_subparsers.add_parser("plan"))
    visual_plan_parser.add_argument("task_id")
    visual_audit = _common(visual_subparsers.add_parser("audit"))
    visual_audit.add_argument("--input", required=True, help="Existing QA report JSON.")
    return parser


def _common(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    parser.add_argument("--output", help="Optional repository-relative JSON evidence output.")
    return parser


def _dispatch(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    if args.command == "init":
        report = initialize_control_plane(root, dry_run=args.dry_run)
        return _finish(
            report,
            args,
            "CONTROL PLANE INIT",
            success={"INITIALIZED", "ALREADY_CONFIGURED", "READY", "REVIEW_REQUIRED"},
        )
    if args.command == "discover":
        report = discover_control_plane(root)
        return _finish(report, args, "CONTROL PLANE DISCOVERY", success={"READY", "REVIEW_REQUIRED"})
    if args.command == "validate":
        report = validate_control_plane(root)
        return _finish(report, args, "CONTROL PLANE VALIDATION")
    if args.command == "doctor":
        report = run_control_plane_doctor(root)
        return _finish(report, args, "CONTROL PLANE DOCTOR", success={"PASS", "WARN"})
    if args.command == "health":
        report = control_plane_health(root)
        return _finish(report, args, "CONTROL PLANE HEALTH", success={"PASS", "WARN"})
    if args.command == "program":
        report = program_status(root)
        observed_status = report.get("status")
        if args.program_command == "plan":
            report = {
                **report,
                "mode": "whole-program",
                "commandsExecuted": 0,
            }
        elif args.program_command == "complete" and report.get("status") != "COMPLETE":
            report = {
                **report,
                "status": "BLOCKED",
                "completionClaimed": False,
                "errors": report.get("errors", [])
                + ["Program completion requires every configured control gate and governed backlog item to pass."],
            }
            report["humanSummary"] = report["humanSummary"].replace(
                f"Program status: **{observed_status}**",
                "Program status: **BLOCKED**",
                1,
            )
        return _finish(
            report,
            args,
            "REPOSITORY FINALIZATION PROGRAM",
            success=(
                {"COMPLETE", "IN_PROGRESS", "BLOCKED"}
                if args.program_command in {"status", "plan"}
                else {"COMPLETE"}
            ),
        )
    if args.command == "govern":
        if args.govern_command == "audit":
            report = audit_governance(root)
            return _finish(report, args, "REPOSITORY GOVERNANCE AUDIT", success={"READY", "REVIEW_REQUIRED"})
        if args.govern_command == "plan":
            report = plan_governance_convergence(root)
            report["humanSummary"] = report["audit"]["humanSummary"]
            return _finish(report, args, "REPOSITORY CONVERGENCE PLAN", success={"READY", "REVIEW_REQUIRED"})
        if args.govern_command == "apply":
            report = apply_governance_convergence(root, ratification_path=args.ratification)
            return _finish(report, args, "REPOSITORY CONVERGENCE APPLY", success={"APPLIED_READY", "APPLIED_REVIEW_REQUIRED"})
        report = verify_governance_convergence(root)
        return _finish(report, args, "REPOSITORY CONVERGENCE VERIFY")
    if args.command == "planes":
        from .control_plane import load_manifest

        report = audit_planes(root, load_manifest(root))
        return _finish(report, args, "PLANE AUDIT", success={"PASS", "WARN"})
    if args.command == "backlog":
        from .control_plane import load_manifest

        manifest = load_manifest(root)
        config = manifest["spec"]["planes"]["intent"]["backlog"]
        report = audit_backlog(root, config)
        if args.backlog_command == "plan":
            report = {
                **report,
                "mode": "dependency-waves",
                "claimBoundary": "Every declared non-historical item is represented; execution remains authority-bound.",
            }
        elif args.backlog_command == "complete" and (
            report.get("status") != "PASS" or report.get("completion") != "COMPLETE"
        ):
            report = {
                **report,
                "status": "FAIL",
                "errors": report.get("errors", []) + [
                    "Whole-backlog completion gate requires every governed item to be terminal"
                ],
            }
        return _finish(report, args, "WHOLE BACKLOG", success={"PASS"})
    if args.command == "intelligence":
        report = route_task_by_id(root, args.task_id)
        return _finish(report, args, "INTELLIGENCE ROUTE")
    if args.command == "architecture":
        if args.architecture_command == "graph":
            report = architecture_graph(root)
            if args.summary:
                report = _architecture_graph_summary(report)
            return _finish(report, args, "ARCHITECTURE GRAPH")
        report = architecture_impact(root, args.task_id, changed_paths=args.changed or None)
        return _finish(report, args, "ARCHITECTURE IMPACT")
    if args.command == "task":
        if args.task_command == "create":
            report = create_task(root, _load_json(args.input))
            return _finish(report, args, "TASK PACKET", success={"CREATED"})
        report = task_context(root, args.task_id, max_files=args.max_files)
        return _finish(report, args, "BOUNDED TASK CONTEXT")
    if args.command == "impact":
        report = analyze_impact(root, args.task_id, changed_paths=args.changed or None)
        return _finish(report, args, "CHANGE IMPACT")
    if args.command == "verify":
        report = analyze_impact(root, args.task_id, changed_paths=args.changed or None)
        report = {
            **report,
            "mode": "affected",
            "authority": "plan-only",
            "commandsExecuted": 0,
        }
        return _finish(report, args, "AFFECTED VERIFICATION PLAN")
    if args.command == "design":
        if args.design_command == "inspect":
            report = inspect_design(root)
            return _finish(report, args, "DESIGN INTELLIGENCE ADAPTER")
        if args.design_command == "adoption-audit":
            report = audit_design_adoption(root, args.input)
            return _finish(report, args, "DESIGN ADOPTION AUDIT")
        report = evaluate_design_adoption(
            root,
            args.task,
            references=args.reference,
            images=args.image,
            analysis=_load_json(args.analysis) if args.analysis else None,
            profile_name=args.profile,
            surface=args.surface,
            governance_receipts=args.governance_receipt,
        )
        if args.save_to:
            report["saved"] = save_adoption_bundle(report["report"], args.save_to)
        _emit(report, args, title="DESIGN ADOPTION ADAPTER")
        return 1 if args.strict and report["status"] != "READY" else 0
    if args.command == "visual":
        if args.visual_command == "plan":
            report = visual_plan(root, args.task_id)
            return _finish(report, args, "VISUAL QA PLAN")
        report = audit_visual_evidence(root, args.input)
        return _finish(report, args, "VISUAL QA AUDIT")
    raise ValueError(f"Unhandled command: {args.command}")


def _finish(
    report: dict[str, Any],
    args: argparse.Namespace,
    title: str,
    *,
    success: set[str] | None = None,
) -> int:
    _emit(report, args, title=title)
    accepted = success or {"PASS"}
    return 0 if report.get("status") in accepted else 1


def _architecture_graph_summary(report: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "schemaVersion",
        "status",
        "root",
        "bounded",
        "limits",
        "sourceFilesScanned",
        "discoveredNodeCount",
        "nodeCount",
        "edgeCount",
        "nodeCounts",
        "graphSha256",
        "truncated",
        "claimBoundary",
        "errors",
        "warnings",
    )
    return {field: report[field] for field in fields if field in report}


def _emit(report: dict[str, Any], args: argparse.Namespace, *, title: str) -> None:
    output = getattr(args, "output", None)
    if output:
        destination = ensure_within(Path(args.root).resolve(), output)
        atomic_write_json(destination, report)
        report = {**report, "evidenceOutput": str(destination)}
    if getattr(args, "format", "text") == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report.get("humanSummary"):
        print(report["humanSummary"])
    else:
        print(f"{title}\n\n{json.dumps(report, indent=2, sort_keys=True)}")


def _load_json(path: str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _command_name(args: argparse.Namespace) -> str:
    parts = [getattr(args, "command", None)]
    parts.extend(
        getattr(args, field, None)
        for field in (
            "planes_command",
            "program_command",
            "govern_command",
            "backlog_command",
            "intelligence_command",
            "architecture_command",
            "task_command",
            "verify_command",
            "design_command",
            "visual_command",
        )
    )
    return " ".join(part for part in parts if part)


if __name__ == "__main__":
    raise SystemExit(main())
    control_plane_health,
    discover_control_plane,
    route_task_by_id,
