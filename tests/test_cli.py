from __future__ import annotations

import json
import subprocess
import sys
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


if __name__ == "__main__":
    unittest.main()
