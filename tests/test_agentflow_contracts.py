from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from design_intelligence.agentflow_contracts import (
    audit_agentflow_build_receipt,
    canonical_json_sha256,
    validate_governed_handoff,
    write_governed_handoff,
)
from design_intelligence.cli import main as cli_main


class AgentFlowContractTests(unittest.TestCase):
    def handoff(self) -> dict:
        return {
            "schemaVersion": "1.0.0",
            "kind": "design-intelligence/governed-task-handoff",
            "handoffId": "DI-AF-001",
            "createdAt": "2026-09-12T12:00:00Z",
            "repository": {"baseCommit": "a" * 40},
            "objective": "Deliver a verified contract-first integration.",
            "authority": {
                "status": "APPROVED",
                "approvedBy": "repository-owner",
                "approvedAt": "2026-09-12T12:01:00Z",
                "sources": [{"path": "AGENTS.md", "sha256": "b" * 64}],
            },
            "tasks": [{
                "id": "AF-001",
                "title": "Implement contract",
                "description": "Implement the approved contract.",
                "estimateHours": 1,
                "dependsOn": [],
                "owns": ["src/contracts/"],
                "acceptanceCriteria": ["Contract validates"],
                "validate": ["npm test"],
            }],
            "proof": {
                "requiredEvidence": ["focused tests"],
                "claimBoundary": "Local execution and integration only.",
            },
        }

    def test_approved_handoff_passes(self) -> None:
        self.assertEqual(validate_governed_handoff(self.handoff()), [])

    def test_proposed_handoff_cannot_authorize_execution(self) -> None:
        handoff = self.handoff()
        handoff["authority"] = {"status": "PROPOSED", "sources": handoff["authority"]["sources"]}
        self.assertIn("authority.status must be APPROVED for execution", validate_governed_handoff(handoff))

    def test_export_preserves_proposed_as_non_authoritative(self) -> None:
        handoff = self.handoff()
        handoff["authority"] = {"status": "PROPOSED", "sources": handoff["authority"]["sources"]}
        with tempfile.TemporaryDirectory() as directory:
            report = write_governed_handoff(handoff, Path(directory) / "handoff.json")
        self.assertEqual(report["status"], "PASS")
        self.assertFalse(report["executionAuthorized"])

    def test_cli_creates_and_validates_approved_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            output = root / "handoff.json"
            source.write_text(json.dumps(self.handoff()), encoding="utf-8")
            with redirect_stdout(StringIO()):
                create_code = cli_main(["agentflow", "handoff-create", "--input", str(source), "--output", str(output), "--format", "json"])
                validate_code = cli_main(["agentflow", "handoff-validate", "--input", str(output), "--format", "json"])
        self.assertEqual(create_code, 0)
        self.assertEqual(validate_code, 0)

    def test_receipt_is_bound_to_exact_handoff(self) -> None:
        handoff = self.handoff()
        receipt = {
            "schemaVersion": "1.0.0",
            "kind": "agentflow/build-receipt",
            "handoff": {"id": handoff["handoffId"], "sha256": canonical_json_sha256(handoff)},
            "build": {"id": "build-1", "status": "completed", "baseCommit": "a" * 40, "integrationCommit": "c" * 40},
            "tasks": [{"id": "AF-001", "status": "integrated", "resultCommit": "d" * 40, "integrationCommit": "c" * 40, "changedFiles": ["src/contracts/index.ts"], "validation": []}],
            "evidence": {"events": [], "artifacts": [], "approvals": []},
            "proofBoundary": "Local execution and integration only.",
            "generatedAt": "2026-09-12T13:00:00Z",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            handoff_path = root / "handoff.json"
            receipt_path = root / "receipt.json"
            handoff_path.write_text(json.dumps(handoff), encoding="utf-8")
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            audit = audit_agentflow_build_receipt(receipt_path, handoff_path=handoff_path)
        self.assertEqual(audit["status"], "PASS")
        self.assertTrue(audit["handoffVerified"])
        self.assertTrue(audit["executionComplete"])


if __name__ == "__main__":
    unittest.main()
