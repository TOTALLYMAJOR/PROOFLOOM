from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from design_intelligence.workflows import (
    build_handoff,
    build_start_packet,
    build_workflow,
    discover_evidence,
)


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
        self.assertIn("Repository style authorities", handoff["prompt"])

    def test_start_packet_includes_best_practices_and_style_sources(self) -> None:
        packet = build_start_packet(
            str(FIXTURES / "mature-repo"),
            "Improve proposal comparison",
            "quotepilot",
            "Proposal comparison",
            references=["https://aura.build"],
        )
        self.assertEqual(packet["status"], "DIRECTION_REVIEW_REQUIRED")
        self.assertIn("Solve actor, object, goal, decision, state, blocker, authority, and next action", " ".join(packet["workflow"]["best_practices"]))
        self.assertEqual(packet["workflow"]["style_sources"]["repository"]["priority"], "Repository style authority beats admired references.")
        self.assertEqual(packet["workflow"]["style_sources"]["references"]["status"], "RESEARCH_REQUIRED")
        self.assertEqual(len(packet["mission"]["directions"]), 3)
        self.assertEqual(packet["mission"]["referenceLedger"]["status"], "RESEARCH_REQUIRED")
        self.assertEqual(packet["mission"]["referenceLedger"]["entries"][0]["status"], "RESEARCH_REQUIRED")
        self.assertIsNone(packet["mission"]["selectedDirection"])
        self.assertEqual(packet["mission"]["surface"], "Proposal comparison")
        self.assertIn("--profile quotepilot", packet["mission"]["selectionCommand"])
        self.assertIn("--reference https://aura.build", packet["mission"]["selectionCommand"])
        self.assertIn("--save", packet["mission"]["selectionCommand"])

    def test_start_packet_requires_explicit_direction_before_implementation(self) -> None:
        packet = build_start_packet(
            str(FIXTURES / "mature-repo"),
            "Improve the marketing landing page",
            "quotepilot",
            direction="recommended",
        )
        self.assertEqual(packet["status"], "READY_TO_IMPLEMENT")
        self.assertEqual(packet["mission"]["mode"]["id"], "marketing")
        self.assertEqual(packet["mission"]["selectedDirection"], "value-first-proof")
        self.assertIn("explicitly selected direction", packet["prompt"])

    def test_start_packet_infers_customer_proposal_mode(self) -> None:
        packet = build_start_packet(
            str(FIXTURES / "mature-repo"),
            "Improve the customer proposal review and acceptance experience",
            "quotepilot",
        )
        self.assertEqual(packet["mission"]["mode"]["id"], "customer-proposal")
        self.assertTrue(packet["mission"]["mode"]["inferred"])
        self.assertEqual(packet["mission"]["recommendedDirection"], "decision-first-proposal")

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

    def test_cli_start_can_write_handoff_and_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            contract = Path(directory) / "contract.json"
            handoff = Path(directory) / "handoff.md"
            result = subprocess.run(
                [
                    sys.executable, "-m", "design_intelligence.cli", "start",
                    str(FIXTURES / "mature-repo"),
                    "Improve proposal comparison",
                    "--profile", "quotepilot",
                    "--reference", "https://aura.build",
                    "--direction", "recommended",
                    "--contract-out", str(contract),
                    "--output", str(handoff),
                    "--format", "json",
                ],
                cwd=ROOT, capture_output=True, text=True, check=True,
            )
            payload = json.loads(result.stdout)
            self.assertTrue(contract.is_file())
            self.assertTrue(handoff.is_file())
            self.assertEqual(payload["workflow"]["contract"]["taskId"], "improve-proposal-comparison")
            self.assertIn("Style research order", handoff.read_text(encoding="utf-8"))

    def test_cli_start_refuses_contract_before_direction_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            contract = Path(directory) / "contract.json"
            result = subprocess.run(
                [
                    sys.executable, "-m", "design_intelligence.cli", "start",
                    str(FIXTURES / "mature-repo"),
                    "Improve proposal comparison",
                    "--contract-out", str(contract),
                ],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(contract.exists())
            self.assertIn("requires an explicit --direction", result.stderr)

    def test_cli_accepts_plain_english_task_as_the_command(self) -> None:
        result = subprocess.run(
            [
                sys.executable, "-m", "design_intelligence.cli",
                "Improve the marketing landing page",
                "--root", str(FIXTURES / "mature-repo"),
                "--profile", "quotepilot",
                "--format", "json",
            ],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "DIRECTION_REVIEW_REQUIRED")
        self.assertEqual(payload["mission"]["mode"]["id"], "marketing")

    def test_cli_plain_english_task_does_not_require_a_named_profile(self) -> None:
        result = subprocess.run(
            [
                sys.executable, "-m", "design_intelligence.cli",
                "Improve the marketing landing page",
                "--root", str(FIXTURES / "mature-repo"),
                "--format", "json",
            ],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        payload = json.loads(result.stdout)
        self.assertIsNone(payload["profile"])
        self.assertEqual(payload["workflow"]["contract"]["product"], "mature-repo")

    def test_cli_save_writes_a_predictable_mission_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "mission"
            result = subprocess.run(
                [
                    sys.executable, "-m", "design_intelligence.cli",
                    "Improve the marketing landing page",
                    "--root", str(FIXTURES / "mature-repo"),
                    "--profile", "quotepilot",
                    "--direction", "recommended",
                    "--save-to", str(output),
                    "--format", "json",
                ],
                cwd=ROOT, capture_output=True, text=True, check=True,
            )
            payload = json.loads(result.stdout)
            self.assertTrue((output / "mission.json").is_file())
            self.assertTrue((output / "reference-ledger.json").is_file())
            self.assertTrue((output / "handoff.md").is_file())
            self.assertTrue((output / "design-contract.json").is_file())
            self.assertEqual(payload["saved"]["directory"], str(output.resolve()))


if __name__ == "__main__":
    unittest.main()
