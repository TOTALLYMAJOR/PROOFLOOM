from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .assessment import assess_repository, render_assessment_text
from .adoption import (
    audit_adoption_report,
    default_adoption_bundle_path,
    evaluate_adoption,
    render_adoption_text,
    save_adoption_bundle,
)
from .agentflow_contracts import (
    audit_agentflow_build_receipt,
    audit_governed_handoff_repository,
    load_governed_handoff,
    write_governed_handoff,
)
from .agentic import (
    analyze_ux_state_graph,
    assess_outcome,
    build_authority_capsule,
    evaluate_design_arena,
    simulate_counterfactual,
)
from .baselines import (
    audit_baseline_review_request,
    audit_baselines,
    create_baseline_review_request,
    promote_baseline,
)
from .contracts import create_contract, load_and_validate_contract
from .context import build_context, render_context_text
from .doctor import render_doctor_text, run_doctor
from .evidence import build_evidence_pack, write_evidence_pack
from .linting import render_lint_text, run_lint
from .governance import (
    apply_governance_convergence,
    audit_governance,
    governance_design_preflight,
    plan_governance_convergence,
    verify_governance_convergence,
)
from .migrations import assess_migration, render_migration_text
from .memory import (
    append_debt,
    append_decision,
    append_exception,
    append_outcome,
    audit_memory,
    find_stale_records,
    initialize_memory,
    preflight_memory,
    retrieve_context,
)
from .missions import SURFACE_MODES
from .outcome_lifecycle import (
    audit_outcome_ratification_receipt,
    create_outcome_ratification_receipt,
    promote_outcome_from_receipt,
    retire_promoted_decision,
)
from .quality import load_thresholds, score_quality, write_quality_report
from .references import analyze_references, render_reference_text
from .registry import audit_component_registry, build_component_registry, write_component_registry
from .repair import apply_repair_plan
from .review_lifecycle import (
    audit_baseline_review_receipt,
    create_baseline_review_receipt,
    evaluate_baseline_review_lifecycle,
    preflight_baseline_promotion,
)
from .repository import inspect_repository, render_snapshot_text
from .reviewing import render_review_text, review_manifest
from .self_audit import run_self_audit
from .storage import atomic_write_json
from .validation import render_validation_text, validate_repository
from .workflows import (
    build_handoff,
    build_start_packet,
    build_workflow,
    render_workflow_text,
    save_start_packet,
    write_contract_from_workflow,
    write_handoff,
)


COMMANDS = {
    "inspect", "assess", "context", "lint", "refactor-risk", "review", "validate", "doctor",
    "reference", "start", "work", "handoff", "memory", "contract", "registry", "quality",
    "baseline", "repair", "self-audit", "adopt", "adoption-audit", "govern", "agentflow", "agentic", "shell",
}


def main(argv: list[str] | None = None) -> int:
    normalized_argv = _normalize_argv(list(sys.argv[1:] if argv is None else argv))
    parser = argparse.ArgumentParser(prog="design-intelligence")
    subparsers = parser.add_subparsers(dest="command", required=True)

    shell_parser = subparsers.add_parser("shell", help="Start the loopback-only Proofloom operator shell.")
    shell_parser.add_argument("--root", default=".", help="Repository root to bind for this shell session.")
    shell_parser.add_argument("--host", choices=("127.0.0.1", "localhost"), default="127.0.0.1")
    shell_parser.add_argument("--port", type=int, default=8787)
    shell_parser.add_argument("--open", action="store_true", help="Open the shell in the default browser.")

    _add_root_format_parser(subparsers, "inspect")
    _add_root_format_parser(subparsers, "assess")
    govern_parser = subparsers.add_parser("govern")
    govern_subparsers = govern_parser.add_subparsers(dest="govern_command", required=True)
    for command in ("audit", "plan", "verify"):
        _add_root_format_parser(govern_subparsers, command)
    govern_apply = _add_root_format_parser(govern_subparsers, "apply")
    govern_apply.add_argument(
        "--ratification",
        help="Owner-approved authority-drift ratification JSON required when rebasing changed critical authority.",
    )
    context_parser = _add_root_format_parser(subparsers, "context")
    context_parser.add_argument("--profile", choices=("quotepilot", "quietpilot", "leaguepilot"))
    context_parser.add_argument("--brief-file", help="Optional JSON file with actor/task fields.")

    lint_parser = _add_root_format_parser(subparsers, "lint")
    lint_parser.add_argument("--strict", action="store_true", help="Fail the process if lint status is FAIL.")
    lint_parser.add_argument("--scope", action="append", help="Repository-relative file or directory to lint; repeatable.")

    risk_parser = _add_root_format_parser(subparsers, "refactor-risk")
    risk_parser.add_argument("--strict", action="store_true", help="Fail the process if runtime posture is CONVERGE or RESTRUCTURE.")

    review_parser = subparsers.add_parser("review")
    review_parser.add_argument("--input", required=True, help="JSON manifest containing visual-review findings.")
    review_parser.add_argument("--format", choices=("json", "text"), default="text")

    validate_parser = _add_root_format_parser(subparsers, "validate")
    validate_parser.add_argument("--review-input", help="Optional JSON manifest to include visual review evidence.")
    validate_parser.add_argument("--contract-file", help="Optional validated design contract JSON.")
    validate_parser.add_argument("--qa-report", help="Optional Playwright QA report for deterministic quality scoring.")
    validate_parser.add_argument("--thresholds", help="Optional quality thresholds JSON.")
    validate_parser.add_argument("--memory-product")
    validate_parser.add_argument("--memory-archetype")
    validate_parser.add_argument("--memory-surface")
    validate_parser.add_argument("--memory-component")
    validate_parser.add_argument("--scope", action="append", help="Repository-relative file or directory to lint; repeatable.")
    validate_parser.add_argument("--evidence-pack-out", help="Optional output path (.json or .md) for an evidence pack.")

    doctor_parser = _add_root_format_parser(subparsers, "doctor")
    doctor_parser.add_argument("--strict", action="store_true", help="Fail the process if blockers or failing lint are present.")

    reference_parser = subparsers.add_parser("reference")
    reference_parser.add_argument("--input", required=True, help="JSON file of reference objects.")
    reference_parser.add_argument("--profile", choices=("quotepilot", "quietpilot", "leaguepilot"))
    reference_parser.add_argument("--format", choices=("json", "text"), default="text")

    adopt_parser = subparsers.add_parser("adopt")
    adopt_parser.add_argument("task", help="The design task that may use supplied references.")
    adopt_parser.add_argument("--root", default=".", help="Repository root to inspect.")
    adopt_parser.add_argument("--profile", choices=("quotepilot", "quietpilot", "leaguepilot"))
    adopt_parser.add_argument("--surface", help="The product surface being changed.")
    adopt_parser.add_argument("--reference", action="append", help="Reference URL; repeatable.")
    adopt_parser.add_argument("--image", action="append", help="Repository-relative reference image; repeatable.")
    adopt_parser.add_argument("--analysis", help="Structured reference-analysis JSON from a human or model adapter.")
    adopt_parser.add_argument(
        "--governance-receipt",
        action="append",
        help="Governed human review receipt; repeatable and replay-audited.",
    )
    adopt_parser.add_argument("--save", action="store_true", help="Save a governed adoption bundle.")
    adopt_parser.add_argument("--save-to", help="Repository-relative adoption bundle directory.")
    adopt_parser.add_argument("--strict", action="store_true", help="Exit nonzero unless implementation is ready.")
    adopt_parser.add_argument("--format", choices=("json", "text"), default="text")

    adoption_audit = _add_root_format_parser(subparsers, "adoption-audit")
    adoption_audit.add_argument("--input", required=True)

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("root_or_task", help="Plain-English task, or repository root in the legacy two-argument form.")
    start_parser.add_argument("task", nargs="?", help="Plain-English task when a repository root is supplied first.")
    start_parser.add_argument("--root", dest="start_root", help="Repository root; defaults to the current directory.")
    start_parser.add_argument("--profile", choices=("quotepilot", "quietpilot", "leaguepilot"))
    start_parser.add_argument("--surface", help="The product surface being changed.")
    start_parser.add_argument("--mode", choices=SURFACE_MODES, help="Override the inferred surface mode.")
    start_parser.add_argument("--direction", help="Explicit direction ID, or 'recommended'.")
    start_parser.add_argument("--brief-file", help="Optional JSON actor/task fields.")
    start_parser.add_argument("--reference", action="append", help="External reference URL or repo; repeatable.")
    start_parser.add_argument("--image", action="append", help="Repository-relative reference image; repeatable.")
    start_parser.add_argument("--adoption-report", help="Replay-audited READY adoption report for supplied references.")
    start_parser.add_argument("--adapter", choices=("codex", "claude"), default="codex")
    start_parser.add_argument("--contract-out", help="Explicit path for a validated design contract JSON.")
    start_parser.add_argument("--output", help="Explicit Markdown or JSON output path for the handoff.")
    start_parser.add_argument("--save", action="store_true", help="Write a mission bundle under artifacts/design/missions/<task>.")
    start_parser.add_argument("--save-to", help="Write the mission bundle to this explicit directory.")
    start_parser.add_argument("--format", choices=("json", "text"), default="text")

    work_parser = _add_root_format_parser(subparsers, "work")
    work_parser.add_argument("--task", required=True, help="The material design task to organize.")
    work_parser.add_argument("--profile", choices=("quotepilot", "quietpilot", "leaguepilot"))
    work_parser.add_argument("--surface", help="The product surface being changed.")
    work_parser.add_argument("--brief-file", help="Optional JSON actor/task fields.")
    work_parser.add_argument("--reference", action="append", help="External reference URL or name; repeatable.")
    work_parser.add_argument("--contract-out", help="Explicit path for a validated design contract JSON.")

    handoff_parser = _add_root_format_parser(subparsers, "handoff")
    handoff_parser.add_argument("--task", required=True, help="The material design task to hand to an agent.")
    handoff_parser.add_argument("--profile", choices=("quotepilot", "quietpilot", "leaguepilot"))
    handoff_parser.add_argument("--surface", help="The product surface being changed.")
    handoff_parser.add_argument("--brief-file", help="Optional JSON actor/task fields.")
    handoff_parser.add_argument("--reference", action="append", help="External reference URL or name; repeatable.")
    handoff_parser.add_argument("--adapter", choices=("codex", "claude"), default="codex")
    handoff_parser.add_argument("--output", help="Explicit Markdown or JSON output path.")

    memory_parser = subparsers.add_parser("memory")
    memory_subparsers = memory_parser.add_subparsers(dest="memory_command", required=True)
    memory_init = _add_root_format_parser(memory_subparsers, "init")
    memory_init.add_argument("--integrate-existing", action="store_true")
    memory_init.add_argument(
        "--memory-only",
        action="store_true",
        help="Install institutional-memory files without quality or baseline infrastructure.",
    )
    memory_context = _add_root_format_parser(memory_subparsers, "context")
    memory_context.add_argument("--product")
    memory_context.add_argument("--archetype")
    memory_context.add_argument("--surface")
    memory_context.add_argument("--component")
    memory_context.add_argument("--max-records", type=int, default=40)
    memory_preflight = _add_root_format_parser(memory_subparsers, "preflight")
    memory_preflight.add_argument("--product")
    memory_preflight.add_argument("--archetype")
    memory_preflight.add_argument("--surface")
    memory_preflight.add_argument("--component")
    memory_preflight.add_argument("--max-records", type=int, default=40)
    memory_preflight.add_argument("--as-of", help="Evaluate freshness as of YYYY-MM-DD.")
    for command in ("add-decision", "add-outcome", "add-exception", "add-debt"):
        memory_write = _add_root_format_parser(memory_subparsers, command)
        memory_write.add_argument("--input", required=True)
    _add_root_format_parser(memory_subparsers, "audit")
    _add_root_format_parser(memory_subparsers, "stale")

    contract_parser = subparsers.add_parser("contract")
    contract_subparsers = contract_parser.add_subparsers(dest="contract_command", required=True)
    contract_create = contract_subparsers.add_parser("create")
    contract_create.add_argument("--input", required=True)
    contract_create.add_argument("--output", required=True)
    contract_create.add_argument("--format", choices=("json", "text"), default="text")
    contract_validate = contract_subparsers.add_parser("validate")
    contract_validate.add_argument("--input", required=True)
    contract_validate.add_argument("--format", choices=("json", "text"), default="text")

    agentflow_parser = subparsers.add_parser("agentflow")
    agentflow_subparsers = agentflow_parser.add_subparsers(dest="agentflow_command", required=True)
    agentflow_create = agentflow_subparsers.add_parser("handoff-create")
    agentflow_create.add_argument("--input", required=True, help="Governed handoff source JSON.")
    agentflow_create.add_argument("--output", required=True, help="Explicit output path for the versioned handoff.")
    agentflow_create.add_argument("--repository", help="Repository root used to re-verify an approved handoff.")
    agentflow_create.add_argument("--format", choices=("json", "text"), default="text")
    agentflow_validate = agentflow_subparsers.add_parser("handoff-validate")
    agentflow_validate.add_argument("--input", required=True)
    agentflow_validate.add_argument("--allow-proposed", action="store_true")
    agentflow_validate.add_argument("--repository", help="Repository root used to verify current authority state.")
    agentflow_validate.add_argument("--format", choices=("json", "text"), default="text")
    agentflow_receipt = agentflow_subparsers.add_parser("receipt-audit")
    agentflow_receipt.add_argument("--input", required=True, help="AgentFlow build receipt JSON.")
    agentflow_receipt.add_argument("--handoff", required=True, help="Exact governed handoff JSON.")
    agentflow_receipt.add_argument("--format", choices=("json", "text"), default="text")

    agentic_parser = subparsers.add_parser("agentic")
    agentic_subparsers = agentic_parser.add_subparsers(dest="agentic_command", required=True)
    agentic_capsule = _add_agentic_input_parser(agentic_subparsers, "capsule")
    agentic_capsule.add_argument("--root", default=".", help="Repository root used to verify authority sources.")
    agentic_capsule.add_argument("--phase", help="Override the input's agent phase.")
    agentic_capsule.add_argument("--max-claims", type=int, help="Override the bounded claim count (1-100).")
    agentic_capsule.add_argument("--as-of", help="Evaluate source freshness at an ISO-8601 datetime.")
    _add_agentic_input_parser(agentic_subparsers, "state-graph")
    _add_agentic_input_parser(agentic_subparsers, "simulate")
    _add_agentic_input_parser(agentic_subparsers, "arena")
    agentic_outcome = _add_agentic_input_parser(agentic_subparsers, "outcome")
    agentic_outcome.add_argument("--as-of", help="Evaluate the observation window at an ISO-8601 datetime.")
    agentic_ratify = _add_root_format_parser(agentic_subparsers, "outcome-ratify")
    agentic_ratify.add_argument("--assessment", required=True, help="Exact outcome assessment JSON.")
    agentic_ratify.add_argument("--decision", required=True, help="Human ratification decision JSON.")
    agentic_ratify.add_argument("--output", required=True, help="Append-only receipt path.")
    agentic_ratify.add_argument("--as-of", help="Ratification time as an ISO-8601 datetime.")
    agentic_ratification_audit = _add_root_format_parser(agentic_subparsers, "outcome-ratification-audit")
    agentic_ratification_audit.add_argument("--input", required=True, help="Outcome ratification receipt JSON.")
    agentic_ratification_audit.add_argument("--as-of", help="Audit time as an ISO-8601 datetime.")
    agentic_promote = _add_root_format_parser(agentic_subparsers, "outcome-promote")
    agentic_promote.add_argument("--receipt", required=True, help="Passing human ratification receipt JSON.")
    agentic_promote.add_argument("--as-of", help="Promotion time as an ISO-8601 datetime.")
    agentic_retire = _add_root_format_parser(agentic_subparsers, "outcome-retire")
    agentic_retire.add_argument("--input", required=True, help="Human retirement decision JSON.")
    agentic_retire.add_argument("--as-of", help="Retirement time as an ISO-8601 datetime.")

    registry_parser = subparsers.add_parser("registry")
    registry_subparsers = registry_parser.add_subparsers(dest="registry_command", required=True)
    registry_scan = _add_root_format_parser(registry_subparsers, "scan")
    registry_scan.add_argument("--output")
    registry_scan.add_argument("--write", action="store_true")
    _add_root_format_parser(registry_subparsers, "audit")

    quality_parser = subparsers.add_parser("quality")
    quality_parser.add_argument("--input", required=True, help="Playwright QA report JSON.")
    quality_parser.add_argument("--thresholds")
    quality_parser.add_argument("--latest-out")
    quality_parser.add_argument("--history-out")
    quality_parser.add_argument("--format", choices=("json", "text"), default="text")

    baseline_parser = subparsers.add_parser("baseline")
    baseline_subparsers = baseline_parser.add_subparsers(dest="baseline_command", required=True)
    baseline_promote = _add_root_format_parser(baseline_subparsers, "promote")
    baseline_promote.add_argument("--scenario", required=True)
    baseline_promote.add_argument("--current-root", required=True)
    baseline_promote.add_argument("--approval", required=True)
    baseline_request = _add_root_format_parser(baseline_subparsers, "request")
    baseline_request.add_argument("--scenario", required=True)
    baseline_request.add_argument("--product", required=True)
    baseline_request.add_argument("--qa-report", required=True)
    baseline_request.add_argument("--model-review", required=True)
    baseline_request.add_argument("--candidate-root", required=True)
    baseline_request.add_argument("--requested-by", required=True)
    baseline_request.add_argument("--output", required=True)
    baseline_request_audit = _add_root_format_parser(baseline_subparsers, "request-audit")
    baseline_request_audit.add_argument("--input", required=True)
    baseline_decide = _add_root_format_parser(baseline_subparsers, "decide")
    baseline_decide.add_argument("--request", required=True)
    baseline_decide.add_argument("--decision", required=True)
    baseline_decide.add_argument("--output", required=True)
    baseline_receipt_audit = _add_root_format_parser(baseline_subparsers, "receipt-audit")
    baseline_receipt_audit.add_argument("--input", required=True)
    baseline_receipt_audit.add_argument("--as-of")
    baseline_preflight = _add_root_format_parser(baseline_subparsers, "preflight")
    baseline_preflight.add_argument("--receipt", required=True)
    baseline_preflight.add_argument("--as-of")
    baseline_lifecycle = _add_root_format_parser(baseline_subparsers, "lifecycle")
    baseline_lifecycle.add_argument("--requests-root", default="artifacts/design/baseline-requests")
    baseline_lifecycle.add_argument("--receipts-root", default="artifacts/design/baseline-decisions")
    baseline_lifecycle.add_argument("--as-of")
    _add_root_format_parser(baseline_subparsers, "audit")

    repair_parser = _add_root_format_parser(subparsers, "repair")
    repair_parser.add_argument("--plan", required=True)
    repair_parser.add_argument("--evidence", required=True)
    repair_parser.add_argument("--iteration", required=True, type=int)
    repair_parser.add_argument("--apply", action="store_true")

    _add_root_format_parser(subparsers, "self-audit")

    args = parser.parse_args(normalized_argv)
    return _dispatch(args)


def _add_root_format_parser(subparsers, name: str):
    sub = subparsers.add_parser(name)
    sub.add_argument("root_positional", nargs="?", default=None, help="Optional repository root.")
    sub.add_argument("--root", default=".", help="Repository root to inspect.")
    sub.add_argument("--format", choices=("json", "text"), default="text")
    return sub


def _add_agentic_input_parser(subparsers, name: str):
    sub = subparsers.add_parser(name)
    sub.add_argument("--input", required=True, help="Capability input JSON.")
    sub.add_argument("--output", help="Optional explicit JSON output path.")
    sub.add_argument("--format", choices=("json", "text"), default="text")
    return sub


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "shell":
        from .operator_shell import serve_operator_shell

        return serve_operator_shell(args.root, args.host, args.port, args.open)
    if args.command == "inspect":
        root = args.root if args.root != "." or args.root_positional is None else args.root_positional
        snapshot = inspect_repository(root or ".")
        return _emit(snapshot.to_dict(), render_snapshot_text(snapshot), args.format)
    if args.command == "assess":
        root = args.root if args.root != "." or args.root_positional is None else args.root_positional
        assessment = assess_repository(root or ".")
        return _emit(assessment.to_dict(), render_assessment_text(assessment), args.format)
    if args.command == "govern":
        root = _root_arg(args)
        if args.govern_command == "audit":
            report = audit_governance(root)
            text = report["humanSummary"]
        elif args.govern_command == "plan":
            report = plan_governance_convergence(root)
            text = report["audit"]["humanSummary"]
        elif args.govern_command == "apply":
            report = apply_governance_convergence(root, ratification_path=args.ratification)
            text = _simple_text("REPOSITORY CONVERGENCE APPLY", report)
        else:
            report = verify_governance_convergence(root)
            text = _simple_text("REPOSITORY CONVERGENCE VERIFY", report)
        _emit(report, text, args.format)
        accepted = {"READY", "REVIEW_REQUIRED", "APPLIED_READY", "APPLIED_REVIEW_REQUIRED", "PASS"}
        return 0 if report.get("status") in accepted else 1
    if args.command == "context":
        root = args.root if args.root != "." or args.root_positional is None else args.root_positional
        context = build_context(root or ".", args.profile, _load_json(args.brief_file))
        return _emit(context.to_dict(), render_context_text(context), args.format)
    if args.command == "lint":
        root = args.root if args.root != "." or args.root_positional is None else args.root_positional
        report = run_lint(root or ".", args.scope)
        code = 1 if args.strict and report.status.value == "FAIL" else 0
        _emit(report.to_dict(), render_lint_text(report), args.format)
        return code
    if args.command == "refactor-risk":
        root = args.root if args.root != "." or args.root_positional is None else args.root_positional
        report = assess_migration(inspect_repository(root or "."))
        strict_fail = args.strict and report.runtime_posture.value in {"CONVERGE", "RESTRUCTURE"}
        _emit(report.to_dict(), render_migration_text(report), args.format)
        return 1 if strict_fail else 0
    if args.command == "review":
        report = review_manifest(_load_json_required(args.input))
        return _emit(report.to_dict(), render_review_text(report), args.format)
    if args.command == "validate":
        root = args.root if args.root != "." or args.root_positional is None else args.root_positional
        review_data = _load_json(args.review_input)
        report = validate_repository(root or ".", review_data, args.scope)
        contract_data = None
        contract_errors: list[str] = []
        if args.contract_file:
            contract_data, contract_errors = load_and_validate_contract(args.contract_file)
            if contract_errors:
                report.status = type(report.status).FAIL
                report.notes.append("Design contract validation failed.")
        quality_data = None
        if args.qa_report:
            quality_object = score_quality(_load_json_required(args.qa_report), load_thresholds(args.thresholds))
            quality_data = quality_object.to_dict()
            if quality_object.status.value != "PASS":
                report.status = type(report.status).FAIL
                report.notes.append("Deterministic design quality gates failed.")
        memory_data = None
        if any((args.memory_product, args.memory_archetype, args.memory_surface, args.memory_component)):
            memory_data = retrieve_context(
                root or ".",
                product=args.memory_product,
                archetype=args.memory_archetype,
                surface=args.memory_surface,
                component=args.memory_component,
            ).to_dict()
        if args.evidence_pack_out:
            pack = build_evidence_pack(
                report.assessment,
                report,
                contract=contract_data,
                review_manifest=review_data,
                quality_report=quality_data,
                memory_context=memory_data,
            )
            write_evidence_pack(pack, args.evidence_pack_out)
        payload = report.to_dict()
        payload.update({"contract_errors": contract_errors, "quality_report": quality_data, "memory_context": memory_data})
        return _emit(payload, render_validation_text(report), args.format)
    if args.command == "doctor":
        root = args.root if args.root != "." or args.root_positional is None else args.root_positional
        report = run_doctor(root or ".")
        strict_fail = args.strict and (report.blockers or report.lint_report.status.value == "FAIL")
        _emit(report.to_dict(), render_doctor_text(report), args.format)
        return 1 if strict_fail else 0
    if args.command == "reference":
        report = analyze_references(_load_json_required(args.input), args.profile)
        return _emit(report.to_dict(), render_reference_text(report), args.format)
    if args.command == "adopt":
        preflight = governance_design_preflight(args.root)
        if preflight["status"] != "PASS":
            report = {
                "status": "BLOCKED",
                "implementationReady": False,
                "reason": "Repository understanding and governance must converge before design adoption.",
                "governancePreflight": preflight,
            }
            _emit(report, _governance_block_text(preflight), args.format)
            return 1
        report = evaluate_adoption(
            args.root,
            args.task,
            references=args.reference,
            images=args.image,
            analysis=_load_json(args.analysis),
            profile_name=args.profile,
            surface=args.surface,
            governance_receipts=args.governance_receipt,
        )
        payload = dict(report)
        if args.save or args.save_to:
            output = args.save_to or default_adoption_bundle_path(args.root, args.task)
            payload["saved"] = save_adoption_bundle(report, output)
        _emit(payload, render_adoption_text(report), args.format)
        return 1 if args.strict and not report["implementationReady"] else 0
    if args.command == "adoption-audit":
        report = audit_adoption_report(_root_arg(args), args.input)
        _emit(report, _simple_text("DESIGN ADOPTION AUDIT", report), args.format)
        return 0 if report["status"] == "PASS" else 1
    if args.command == "start":
        root, task = _start_args(args)
        preflight = governance_design_preflight(root)
        if preflight["status"] != "PASS":
            report = {
                "status": "GOVERNANCE_REQUIRED",
                "task": task,
                "root": str(Path(root).resolve()),
                "governancePreflight": preflight,
                "nextAction": f"design-intelligence govern plan --root {Path(root).resolve()}",
            }
            _emit(report, _governance_block_text(preflight), args.format)
            return 1
        packet = build_start_packet(
            root,
            task,
            args.profile,
            args.surface,
            _load_json(args.brief_file),
            args.reference,
            args.adapter,
            args.mode,
            args.direction,
            args.adoption_report,
            args.image,
        )
        if args.contract_out:
            if not packet["mission"]["selectedDirection"]:
                raise ValueError("--contract-out requires an explicit --direction selection")
            if not packet["mission"].get("implementationReady"):
                raise ValueError("--contract-out requires a READY adoption report for supplied references")
            write_contract_from_workflow(packet["workflow"], args.contract_out)
            packet["contract_output"] = str(Path(args.contract_out).resolve())
        if args.output:
            write_handoff(packet["handoff"], args.output)
            packet["output"] = str(Path(args.output).resolve())
        if args.save or args.save_to:
            packet["saved"] = save_start_packet(packet, args.save_to)
        text = packet["prompt"] if packet["status"] == "READY_TO_IMPLEMENT" else packet["summary"]
        return _emit(packet, text, args.format)
    if args.command == "work":
        preflight = governance_design_preflight(_root_arg(args))
        if preflight["status"] != "PASS":
            _emit(preflight, _governance_block_text(preflight), args.format)
            return 1
        workflow = build_workflow(
            _root_arg(args), args.task, args.profile, args.surface, _load_json(args.brief_file), args.reference
        )
        if args.contract_out:
            write_contract_from_workflow(workflow, args.contract_out)
            workflow["contract_output"] = str(Path(args.contract_out).resolve())
        return _emit(workflow, render_workflow_text(workflow), args.format)
    if args.command == "handoff":
        preflight = governance_design_preflight(_root_arg(args))
        if preflight["status"] != "PASS":
            _emit(preflight, _governance_block_text(preflight), args.format)
            return 1
        workflow = build_workflow(
            _root_arg(args), args.task, args.profile, args.surface, _load_json(args.brief_file), args.reference
        )
        packet = build_handoff(workflow, args.adapter)
        if args.output:
            write_handoff(packet, args.output)
            packet["output"] = str(Path(args.output).resolve())
        return _emit(packet, packet["prompt"], args.format)
    if args.command == "memory":
        root = _root_arg(args)
        if args.memory_command == "init":
            report = initialize_memory(root, args.integrate_existing, args.memory_only)
        elif args.memory_command == "context":
            report = retrieve_context(
                root,
                product=args.product,
                archetype=args.archetype,
                surface=args.surface,
                component=args.component,
                max_records=args.max_records,
            ).to_dict()
        elif args.memory_command == "preflight":
            report = preflight_memory(
                root,
                product=args.product,
                archetype=args.archetype,
                surface=args.surface,
                component=args.component,
                max_records=args.max_records,
                as_of=_parse_date(args.as_of),
            )
        elif args.memory_command == "add-decision":
            report = append_decision(root, _load_json_required(args.input))
        elif args.memory_command == "add-outcome":
            report = append_outcome(root, _load_json_required(args.input))
        elif args.memory_command == "add-exception":
            report = append_exception(root, _load_json_required(args.input))
        elif args.memory_command == "add-debt":
            report = append_debt(root, _load_json_required(args.input))
        elif args.memory_command == "audit":
            report = audit_memory(root)
        else:
            report = {"status": "PASS", "stale": find_stale_records(root)}
        _emit(report, _simple_text("DESIGN MEMORY", report), args.format)
        if args.memory_command == "audit":
            return 0 if report.get("status") == "PASS" else 1
        if args.memory_command == "preflight":
            return 1 if report.get("status") == "BLOCK" else 0
        return 0
    if args.command == "contract":
        if args.contract_command == "create":
            report = create_contract(_load_json_required(args.input), args.output)
            report = {"status": "PASS", "output": str(Path(args.output).resolve()), "contract": report}
        else:
            contract, errors = load_and_validate_contract(args.input)
            report = {"status": "PASS" if not errors else "FAIL", "errors": errors, "contract": contract}
        _emit(report, _simple_text("DESIGN CONTRACT", report), args.format)
        return 0 if report["status"] == "PASS" else 1
    if args.command == "agentflow":
        if args.agentflow_command == "handoff-create":
            report = write_governed_handoff(
                _load_json_required(args.input),
                args.output,
                repository_root=args.repository,
            )
        elif args.agentflow_command == "handoff-validate":
            handoff = load_governed_handoff(args.input, require_approved=not args.allow_proposed)
            if args.repository:
                report = audit_governed_handoff_repository(handoff, args.repository)
                report.update({
                    "handoffId": handoff["handoffId"],
                    "authorityStatus": handoff["authority"]["status"],
                    "executionAuthorized": (
                        handoff["authority"]["status"] == "APPROVED"
                        and report["status"] == "PASS"
                        and report["currencyVerified"]
                    ),
                })
            else:
                approved = handoff["authority"]["status"] == "APPROVED"
                report = {
                    "status": "REVIEW_REQUIRED" if approved else "PASS",
                    "handoffId": handoff["handoffId"],
                    "authorityStatus": handoff["authority"]["status"],
                    "currencyVerified": False,
                    "executionAuthorized": False,
                    "errors": (
                        ["Approved handoff was not verified against a current repository snapshot"]
                        if approved else []
                    ),
                }
        else:
            report = audit_agentflow_build_receipt(args.input, handoff_path=args.handoff)
        _emit(report, _simple_text("AGENTFLOW CONTRACT", report), args.format)
        return 0 if report["status"] == "PASS" else 1
    if args.command == "agentic":
        if args.agentic_command == "capsule":
            payload = _load_json_required(args.input)
            report = build_authority_capsule(
                args.root,
                payload,
                phase=args.phase,
                max_claims=args.max_claims,
                as_of=_parse_as_of(args.as_of),
            )
            title = "AUTHORITY CAPSULE"
        elif args.agentic_command == "state-graph":
            report = analyze_ux_state_graph(_load_json_required(args.input))
            title = "UX STATE GRAPH"
        elif args.agentic_command == "simulate":
            report = simulate_counterfactual(_load_json_required(args.input))
            title = "COUNTERFACTUAL DESIGN SIMULATION"
        elif args.agentic_command == "arena":
            report = evaluate_design_arena(_load_json_required(args.input))
            title = "GOVERNED DESIGN ARENA"
        elif args.agentic_command == "outcome":
            report = assess_outcome(_load_json_required(args.input), as_of=_parse_as_of(args.as_of))
            title = "OUTCOME ASSESSMENT"
        elif args.agentic_command == "outcome-ratify":
            report = create_outcome_ratification_receipt(
                _root_arg(args),
                args.assessment,
                _load_json_required(args.decision),
                args.output,
                decided_at=_parse_as_of(args.as_of),
            )
            title = "OUTCOME RATIFICATION"
        elif args.agentic_command == "outcome-ratification-audit":
            report = audit_outcome_ratification_receipt(_root_arg(args), args.input, as_of=_parse_as_of(args.as_of))
            title = "OUTCOME RATIFICATION AUDIT"
        elif args.agentic_command == "outcome-promote":
            report = promote_outcome_from_receipt(_root_arg(args), args.receipt, as_of=_parse_as_of(args.as_of))
            title = "OUTCOME MEMORY PROMOTION"
        else:
            report = retire_promoted_decision(
                _root_arg(args),
                _load_json_required(args.input),
                retired_at=_parse_as_of(args.as_of),
            )
            title = "OUTCOME MEMORY RETIREMENT"
        if getattr(args, "output", None) and args.agentic_command in {"capsule", "state-graph", "simulate", "arena", "outcome"}:
            atomic_write_json(args.output, report)
            report = {**report, "output": str(Path(args.output).resolve())}
        _emit(report, _simple_text(title, report), args.format)
        return 1 if report.get("status") in {"BLOCKED", "FAIL"} else 0
    if args.command == "registry":
        root = _root_arg(args)
        if args.registry_command == "scan":
            report = write_component_registry(root, args.output) if args.write else build_component_registry(root)
        else:
            report = audit_component_registry(root)
        _emit(report, _simple_text("COMPONENT REGISTRY", report), args.format)
        return 1 if args.registry_command == "audit" and report.get("status") != "PASS" else 0
    if args.command == "quality":
        thresholds = load_thresholds(args.thresholds)
        report_object = score_quality(_load_json_required(args.input), thresholds)
        if args.latest_out:
            write_quality_report(report_object, args.latest_out, args.history_out, {"source": args.input})
        report = report_object.to_dict()
        _emit(report, _simple_text("DESIGN QUALITY", report), args.format)
        return 0 if report_object.status.value == "PASS" else 1
    if args.command == "baseline":
        root = _root_arg(args)
        if args.baseline_command == "promote":
            report = promote_baseline(root, args.scenario, args.current_root, args.approval)
        elif args.baseline_command == "request":
            report = create_baseline_review_request(
                root,
                args.scenario,
                args.product,
                args.qa_report,
                args.model_review,
                args.candidate_root,
                args.requested_by,
                args.output,
            )
        elif args.baseline_command == "request-audit":
            report = audit_baseline_review_request(root, args.input)
        elif args.baseline_command == "decide":
            report = create_baseline_review_receipt(
                root,
                args.request,
                _load_json_required(args.decision),
                args.output,
            )
        elif args.baseline_command == "receipt-audit":
            report = audit_baseline_review_receipt(
                root,
                args.input,
                as_of=_parse_as_of(args.as_of),
            )
        elif args.baseline_command == "preflight":
            report = preflight_baseline_promotion(
                root,
                args.receipt,
                as_of=_parse_as_of(args.as_of),
            )
        elif args.baseline_command == "lifecycle":
            report = evaluate_baseline_review_lifecycle(
                root,
                requests_root=args.requests_root,
                receipts_root=args.receipts_root,
                as_of=_parse_as_of(args.as_of),
            )
        else:
            report = audit_baselines(root)
        _emit(report, _simple_text("BASELINE GOVERNANCE", report), args.format)
        if args.baseline_command == "preflight":
            return 0 if report.get("status") == "READY" else 1
        audit_command = args.baseline_command in {
            "audit", "request-audit", "receipt-audit", "lifecycle",
        }
        return 1 if audit_command and report.get("status") != "PASS" else 0
    if args.command == "repair":
        report_object = apply_repair_plan(
            _root_arg(args),
            _load_json_required(args.plan),
            _load_json_required(args.evidence),
            args.iteration,
            apply=args.apply,
        )
        report = report_object.to_dict()
        _emit(report, _simple_text("BOUNDED REPAIR", report), args.format)
        return 0 if report_object.status in {"APPLIED", "DRY_RUN"} else 1
    if args.command == "self-audit":
        report = run_self_audit(_root_arg(args))
        _emit(report, _simple_text("SELF AUDIT", report), args.format)
        return 0 if report["status"] == "PASS" else 1
    raise ValueError(f"Unhandled command: {args.command}")


def _load_json(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    return _load_json_required(path)


def _load_json_required(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _emit(data: dict[str, Any], text: str, fmt: str) -> int:
    if fmt == "json":
        print(json.dumps(data, indent=2))
    else:
        print(text)
    return 0


def _root_arg(args: argparse.Namespace) -> str:
    return args.root if args.root != "." or args.root_positional is None else args.root_positional


def _normalize_argv(argv: list[str]) -> list[str]:
    if argv and not argv[0].startswith("-") and argv[0] not in COMMANDS:
        return ["start", *argv]
    return argv


def _start_args(args: argparse.Namespace) -> tuple[str, str]:
    if args.task is None:
        return args.start_root or ".", args.root_or_task
    return args.start_root or args.root_or_task, args.task


def _simple_text(title: str, report: dict[str, Any]) -> str:
    return f"{title}\n\n" + json.dumps(report, indent=2)


def _governance_block_text(preflight: dict[str, Any]) -> str:
    readiness = preflight.get("finalizationReadiness", {}).get("status", "UNKNOWN")
    lines = [
        "DESIGN IS LOCKED",
        "",
        "The repository must recover and verify its product understanding before design work begins.",
        f"Finalization readiness: {readiness}",
        "",
        "Blocking problems:",
    ]
    errors = preflight.get("errors", [])
    lines.extend(f"- {error}" for error in errors)
    lines.extend(["", "Next: run `design-intelligence govern plan --root <repository>`." ])
    return "\n".join(lines)


def _parse_as_of(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("--as-of must include a timezone")
    return parsed


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


if __name__ == "__main__":
    raise SystemExit(main())
