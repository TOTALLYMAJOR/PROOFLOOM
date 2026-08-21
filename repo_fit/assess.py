from __future__ import annotations

import argparse
import json

from design_intelligence.assessment import assess_repository, render_assessment_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assess repo-fit for a repository.")
    parser.add_argument("root_positional", nargs="?", default=None, help="Optional repository root.")
    parser.add_argument("--root", default=None, help="Repository root to inspect.")
    parser.add_argument("--format", choices=("json", "text"), default="text", help="Output format.")
    args = parser.parse_args(argv)
    root = args.root or args.root_positional or "."
    assessment = assess_repository(root)
    if args.format == "json":
        print(json.dumps(assessment.to_dict(), indent=2))
    else:
        print(render_assessment_text(assessment))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
