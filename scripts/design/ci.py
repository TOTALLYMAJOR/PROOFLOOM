#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable
SKILL_VALIDATOR = Path("/mnt/c/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py")


def main() -> int:
    tier = sys.argv[1] if len(sys.argv) > 1 else "quick"
    if tier not in {"quick", "standard", "full"}:
        print("Usage: ci.py [quick|standard|full]", file=sys.stderr)
        return 2
    commands = quick_commands()
    if tier in {"standard", "full"}:
        commands.extend(standard_commands())
    if tier == "full":
        commands.extend(full_commands())
    for label, command in commands:
        print(f"\n[{tier}] {label}", flush=True)
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            print(f"FAILED: {label} exited {result.returncode}", file=sys.stderr)
            return result.returncode
    print(f"\nDESIGN CI {tier.upper()}: PASS")
    return 0


def quick_commands() -> list[tuple[str, list[str]]]:
    return [
        ("unit and governance tests", [PYTHON, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]),
        ("design contract", [PYTHON, "-m", "design_intelligence.cli", "contract", "validate", "--input", "artifacts/design/briefs/ADD-V2-DEMO.json", "--format", "json"]),
        ("memory integrity", [PYTHON, "-m", "design_intelligence.cli", "memory", "audit", "--root", ".", "--format", "json"]),
        ("baseline integrity", [PYTHON, "-m", "design_intelligence.cli", "baseline", "audit", "--root", ".", "--format", "json"]),
        ("component registry", [PYTHON, "-m", "design_intelligence.cli", "registry", "audit", "--root", ".", "--format", "json"]),
        ("diff whitespace", ["git", "diff", "--check"]),
    ]


def standard_commands() -> list[tuple[str, list[str]]]:
    return [
        ("governed Playwright QA", ["npm", "run", "design:qa"]),
        (
            "deterministic quality score",
            [PYTHON, "-m", "design_intelligence.cli", "quality", "--input", "artifacts/design/reports/design-department-surface/qa-report.json", "--thresholds", ".design/quality/thresholds.json", "--format", "json"],
        ),
        (
            "integrated evidence pack",
            [
                PYTHON, "-m", "design_intelligence.cli", "validate", "--root", ".",
                "--scope", "tests/fixtures/visual-surface",
                "--review-input", "artifacts/design/reports/design-department-surface/review-manifest.json",
                "--contract-file", "artifacts/design/briefs/ADD-V2-DEMO.json",
                "--qa-report", "artifacts/design/reports/design-department-surface/qa-report.json",
                "--thresholds", ".design/quality/thresholds.json",
                "--memory-product", "design-intelligence",
                "--memory-surface", "Design QA Control Deck fixture",
                "--evidence-pack-out", "artifacts/design/evidence/ADD-V2-DEMO/evidence-pack.md",
                "--format", "text",
            ],
        ),
    ]


def full_commands() -> list[tuple[str, list[str]]]:
    commands: list[tuple[str, list[str]]] = [
        ("three rendered repair cycles", ["npm", "run", "design:repair:prove"]),
        ("npm dependency audit", ["npm", "audit", "--audit-level=high"]),
    ]
    if SKILL_VALIDATOR.is_file():
        commands.extend(
            (f"validate skill {skill}", [PYTHON, str(SKILL_VALIDATOR), f"skills/{skill}"])
            for skill in (
                "design-language",
                "ux-architect",
                "reference-intelligence",
                "visual-review",
                "design-linter",
            )
        )
    commands.append(("V2 self-audit", [PYTHON, "-m", "design_intelligence.cli", "self-audit", "--root", ".", "--format", "json"]))
    return commands


if __name__ == "__main__":
    raise SystemExit(main())
