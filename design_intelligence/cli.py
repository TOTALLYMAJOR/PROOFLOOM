from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .assessment import assess_repository, render_assessment_text
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
from .migrations import assess_migration, render_migration_text
from .memory import (
    append_debt,
    append_decision,
    append_exception,
    append_outcome,
    audit_memory,
    find_stale_records,
    initialize_memory,
    retrieve_context,
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
from .validation import render_validation_text, validate_repository


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="design-intelligence")
    subparsers = parser.add_subparsers(dest="command", required=True)

    _add_root_format_parser(subparsers, "inspect")
    _add_root_format_parser(subparsers, "assess")
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

    memory_parser = subparsers.add_parser("memory")
    memory_subparsers = memory_parser.add_subparsers(dest="memory_command", required=True)
    memory_init = _add_root_format_parser(memory_subparsers, "init")
    memory_init.add_argument("--integrate-existing", action="store_true")
    memory_context = _add_root_format_parser(memory_subparsers, "context")
    memory_context.add_argument("--product")
    memory_context.add_argument("--archetype")
    memory_context.add_argument("--surface")
    memory_context.add_argument("--component")
    memory_context.add_argument("--max-records", type=int, default=40)
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

    args = parser.parse_args(argv)
    return _dispatch(args)


def _add_root_format_parser(subparsers, name: str):
    sub = subparsers.add_parser(name)
    sub.add_argument("root_positional", nargs="?", default=None, help="Optional repository root.")
    sub.add_argument("--root", default=".", help="Repository root to inspect.")
    sub.add_argument("--format", choices=("json", "text"), default="text")
    return sub


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "inspect":
        root = args.root if args.root != "." or args.root_positional is None else args.root_positional
        snapshot = inspect_repository(root or ".")
        return _emit(snapshot.to_dict(), render_snapshot_text(snapshot), args.format)
    if args.command == "assess":
        root = args.root if args.root != "." or args.root_positional is None else args.root_positional
        assessment = assess_repository(root or ".")
        return _emit(assessment.to_dict(), render_assessment_text(assessment), args.format)
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
    if args.command == "memory":
        root = _root_arg(args)
        if args.memory_command == "init":
            report = initialize_memory(root, args.integrate_existing)
        elif args.memory_command == "context":
            report = retrieve_context(
                root,
                product=args.product,
                archetype=args.archetype,
                surface=args.surface,
                component=args.component,
                max_records=args.max_records,
            ).to_dict()
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
        return 1 if args.memory_command == "audit" and report.get("status") != "PASS" else 0
    if args.command == "contract":
        if args.contract_command == "create":
            report = create_contract(_load_json_required(args.input), args.output)
            report = {"status": "PASS", "output": str(Path(args.output).resolve()), "contract": report}
        else:
            contract, errors = load_and_validate_contract(args.input)
            report = {"status": "PASS" if not errors else "FAIL", "errors": errors, "contract": contract}
        _emit(report, _simple_text("DESIGN CONTRACT", report), args.format)
        return 0 if report["status"] == "PASS" else 1
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


def _simple_text(title: str, report: dict[str, Any]) -> str:
    return f"{title}\n\n" + json.dumps(report, indent=2)


def _parse_as_of(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("--as-of must include a timezone")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
