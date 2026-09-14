from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from design_intelligence.backlog_assembly import (
    assemble_backlog_brief,
    save_backlog_proposal,
    validate_backlog_proposal,
)


ROOT = Path(__file__).resolve().parents[1]


def valid_proposal() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "kind": "proofloom/backlog-proposal",
        "proposalStatus": "REVIEW_REQUIRED",
        "objective": "Create a complete release backlog",
        "coverage": {
            "sourcesReviewed": [
                {"path": "README.md", "role": "product context", "finding": "Defines the supported workflow."}
            ],
            "journeys": ["Operator prepares and reviews a backlog"],
            "capabilities": ["Backlog proposal validation"],
            "exclusions": ["Production deployment"],
            "unresolvedQuestions": ["Who adopts the proposal?"],
            "completionBoundary": "Tasks cover local implementation and proof, not production adoption.",
        },
        "tasks": [
            {
                "id": "MC-001",
                "title": "Implement proposal validation",
                "description": "Validate the evidence-bound proposal contract.",
                "status": "PROPOSED",
                "dependsOn": [],
                "ownership": ["src/validation"],
                "acceptanceCriteria": ["Invalid dependencies are rejected."],
                "validation": ["python3 -m unittest tests.test_validation"],
                "evidenceRequired": ["Passing focused test output"],
            },
            {
                "id": "MC-002",
                "title": "Expose review workflow",
                "description": "Guide the operator through explicit review and save.",
                "status": "PROPOSED",
                "dependsOn": ["MC-001"],
                "ownership": ["src/operator"],
                "acceptanceCriteria": ["Save remains disabled before validation."],
                "validation": ["npm test"],
                "evidenceRequired": ["Desktop and mobile screenshots"],
            },
        ],
    }


class BacklogAssemblyTests(unittest.TestCase):
    def test_brief_binds_repository_sources_and_output_contract(self) -> None:
        brief = assemble_backlog_brief(ROOT, "Assemble the Master Coach backlog", surface="Coaching workspace")

        self.assertEqual(brief["status"], "AI_BRIEF_READY")
        self.assertEqual(brief["repository"]["root"], str(ROOT))
        self.assertTrue(any(source["path"] == "AGENTS.md" for source in brief["authoritySources"]))
        self.assertIn("Return exactly one JSON object", brief["aiInstruction"])
        self.assertEqual(brief["outputSchema"]["proposalStatus"], "REVIEW_REQUIRED")

    def test_valid_proposal_passes_with_dependency_summary(self) -> None:
        report = validate_backlog_proposal(ROOT, valid_proposal())

        self.assertEqual(report["status"], "VALID")
        self.assertEqual(report["taskCount"], 2)
        self.assertFalse(report["canonical"])
        self.assertFalse(report["executionAuthorized"])

    def test_cycle_and_overlapping_ownership_are_rejected(self) -> None:
        proposal = valid_proposal()
        proposal["tasks"][0]["dependsOn"] = ["MC-002"]
        proposal["tasks"][1]["ownership"] = ["src/validation/rules"]

        report = validate_backlog_proposal(ROOT, proposal)

        self.assertEqual(report["status"], "INVALID")
        self.assertTrue(any("dependency cycle" in error for error in report["errors"]))
        self.assertTrue(any("ownership overlaps" in error for error in report["errors"]))

    def test_shell_control_syntax_and_complete_claims_are_rejected(self) -> None:
        proposal = valid_proposal()
        proposal["tasks"][0]["status"] = "COMPLETE"
        proposal["tasks"][0]["validation"] = ["npm test && npm run deploy"]

        report = validate_backlog_proposal(ROOT, json.dumps(proposal))

        self.assertEqual(report["status"], "INVALID")
        self.assertTrue(any("status must equal PROPOSED" in error for error in report["errors"]))
        self.assertTrue(any("shell control syntax" in error for error in report["errors"]))

    def test_bound_objective_drift_is_rejected(self) -> None:
        report = validate_backlog_proposal(
            ROOT,
            valid_proposal(),
            expected_objective="A different objective",
        )

        self.assertEqual(report["status"], "INVALID")
        self.assertIn("objective must match the repository-bound assembly brief", report["errors"])

    def test_save_is_explicit_bounded_and_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
            report = save_backlog_proposal(root, valid_proposal(), "work/proposed-backlog.json")

            self.assertEqual(report["status"], "SAVED_FOR_REVIEW")
            self.assertFalse(report["canonical"])
            self.assertTrue((root / "work/proposed-backlog.json").is_file())
            with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
                save_backlog_proposal(root, valid_proposal(), "work/proposed-backlog.json")
            with self.assertRaisesRegex(ValueError, "escapes repository root"):
                save_backlog_proposal(root, valid_proposal(), "../outside.json")


if __name__ == "__main__":
    unittest.main()
