from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


class CliTests(unittest.TestCase):
    def test_assess_command_returns_json(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "design_intelligence.cli",
                "assess",
                "--root",
                str(FIXTURES / "mature-repo"),
                "--format",
                "json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["recommendation"], "INTEGRATE")
        self.assertEqual(payload["structure_risk"], "KEEP")

    def test_memory_preflight_emits_allow_and_returns_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("fixture", encoding="utf-8")
            initialize = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "design_intelligence.cli",
                    "memory",
                    "init",
                    "--root",
                    str(root),
                    "--memory-only",
                    "--format",
                    "json",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(json.loads(initialize.stdout)["status"], "READY")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "design_intelligence.cli",
                    "memory",
                    "preflight",
                    "--root",
                    str(root),
                    "--product",
                    "quietpilot",
                    "--surface",
                    "CommandCenter",
                    "--as-of",
                    "2026-08-24",
                    "--format",
                    "json",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            payload = json.loads(result.stdout)

            self.assertEqual(payload["status"], "ALLOW")
            self.assertEqual(payload["scope"]["surface"], "CommandCenter")
            self.assertEqual(payload["blockers"], [])


if __name__ == "__main__":
    unittest.main()
