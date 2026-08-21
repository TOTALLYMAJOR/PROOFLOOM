from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from design_intelligence.workflows import build_handoff, build_workflow, discover_evidence


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


class WorkflowTests(unittest.TestCase):
    def test_workflow_preserves_existing_authority_without_writing(self) -> None:
        workflow = build_workflow(
            str(FIXTURES / "mature-repo"),
            "Improve proposal comparison",
            "quotepilot",
            "Proposal comparison",
        )
        self.assertEqual(workflow["status"], "READY")
        self.assertIn("existing repository instruction authority", workflow["repository"]["preserve"])
        self.assertEqual(workflow["contract"]["surface"], "Proposal comparison")
        self.assertEqual(workflow["contract"]["goal"], "Improve proposal comparison")

    def test_evidence_discovery_uses_existing_artifact_conventions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = root / "artifacts" / "design" / "reports" / "proposal-comparison"
            evidence.mkdir(parents=True)
            (evidence / "review-manifest.json").write_text("{}", encoding="utf-8")
            (evidence / "qa-report.json").write_text("{}", encoding="utf-8")
            discovered = discover_evidence(root, "proposal comparison")
        self.assertEqual(discovered["review_manifests"], ["artifacts/design/reports/proposal-comparison/review-manifest.json"])
        self.assertEqual(discovered["qa_reports"], ["artifacts/design/reports/proposal-comparison/qa-report.json"])

    def test_handoff_is_originality_bounded(self) -> None:
        workflow = build_workflow(str(FIXTURES / "mature-repo"), "Improve proposal comparison", "quotepilot")
        handoff = build_handoff(workflow, "codex")
        self.assertIn("never copy their identity", handoff["prompt"])
        self.assertIn("Do not weaken tests", handoff["prompt"])

    def test_cli_work_can_write_only_an_explicit_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            contract = Path(directory) / "contract.json"
            result = subprocess.run(
                [
                    sys.executable, "-m", "design_intelligence.cli", "work",
                    "--root", str(FIXTURES / "mature-repo"),
                    "--task", "Improve proposal comparison",
                    "--profile", "quotepilot",
                    "--contract-out", str(contract),
                    "--format", "json",
                ],
                cwd=ROOT, capture_output=True, text=True, check=True,
            )
            payload = json.loads(result.stdout)
            self.assertTrue(contract.is_file())
            self.assertEqual(payload["contract"]["taskId"], "improve-proposal-comparison")


if __name__ == "__main__":
    unittest.main()
