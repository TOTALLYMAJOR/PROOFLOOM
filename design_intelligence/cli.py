from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .assessment import assess_repository, render_assessment_text
from .context import build_context, render_context_text
from .doctor import render_doctor_text, run_doctor
from .evidence import build_evidence_pack, write_evidence_pack
from .linting import render_lint_text, run_lint
from .migrations import assess_migration, render_migration_text
from .references import analyze_references, render_reference_text
from .repository import inspect_repository, render_snapshot_text
from .reviewing import render_review_text, review_manifest
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

    risk_parser = _add_root_format_parser(subparsers, "refactor-risk")
    risk_parser.add_argument("--strict", action="store_true", help="Fail the process if runtime posture is CONVERGE or RESTRUCTURE.")

    review_parser = subparsers.add_parser("review")
    review_parser.add_argument("--input", required=True, help="JSON manifest containing visual-review findings.")
    review_parser.add_argument("--format", choices=("json", "text"), default="text")

    validate_parser = _add_root_format_parser(subparsers, "validate")
    validate_parser.add_argument("--review-input", help="Optional JSON manifest to include visual review evidence.")
    validate_parser.add_argument("--evidence-pack-out", help="Optional output path (.json or .md) for an evidence pack.")

    doctor_parser = _add_root_format_parser(subparsers, "doctor")
    doctor_parser.add_argument("--strict", action="store_true", help="Fail the process if blockers or failing lint are present.")

    reference_parser = subparsers.add_parser("reference")
    reference_parser.add_argument("--input", required=True, help="JSON file of reference objects.")
    reference_parser.add_argument("--profile", choices=("quotepilot", "quietpilot", "leaguepilot"))
    reference_parser.add_argument("--format", choices=("json", "text"), default="text")

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
        report = run_lint(root or ".")
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
        report = validate_repository(root or ".", review_data)
        if args.evidence_pack_out:
            pack = build_evidence_pack(report.assessment, report, review_manifest=review_data)
            write_evidence_pack(pack, args.evidence_pack_out)
        return _emit(report.to_dict(), render_validation_text(report), args.format)
    if args.command == "doctor":
        root = args.root if args.root != "." or args.root_positional is None else args.root_positional
        report = run_doctor(root or ".")
        strict_fail = args.strict and (report.blockers or report.lint_report.status.value == "FAIL")
        _emit(report.to_dict(), render_doctor_text(report), args.format)
        return 1 if strict_fail else 0
    if args.command == "reference":
        report = analyze_references(_load_json_required(args.input), args.profile)
        return _emit(report.to_dict(), render_reference_text(report), args.format)
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


if __name__ == "__main__":
    raise SystemExit(main())
