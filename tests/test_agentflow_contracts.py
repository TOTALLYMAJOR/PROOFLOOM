from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import design_intelligence.agentflow_contracts as agentflow_contracts
from design_intelligence.agentflow_contracts import (
    audit_agentflow_build_receipt,
    canonical_json_sha256,
    validate_governed_handoff,
    write_governed_handoff,
)
from design_intelligence.cli import main as cli_main
from design_intelligence.governance import apply_governance_convergence


class AgentFlowContractTests(unittest.TestCase):
    def handoff(self) -> dict:
        return {
            "schemaVersion": "2.0.0",
            "kind": "design-intelligence/governed-task-handoff",
            "handoffId": "DI-AF-001",
            "createdAt": "2026-09-12T12:00:00Z",
            "repository": {
                "baseCommit": "a" * 40,
                "snapshotSha256": "e" * 64,
                "worktreeState": "clean",
            },
            "objective": "Deliver a verified contract-first integration.",
            "authority": {
                "status": "APPROVED",
                "approvedBy": "repository-owner",
                "approvedAt": "2026-09-12T12:01:00Z",
                "stateSha256": "c" * 64,
                "governanceReportSha256": "d" * 64,
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
        handoff["authority"]["status"] = "PROPOSED"
        handoff["authority"].pop("approvedBy")
        handoff["authority"].pop("approvedAt")
        self.assertIn("authority.status must be APPROVED for execution", validate_governed_handoff(handoff))

    def test_export_preserves_proposed_as_non_authoritative(self) -> None:
        handoff = self.handoff()
        handoff["authority"]["status"] = "PROPOSED"
        handoff["authority"].pop("approvedBy")
        handoff["authority"].pop("approvedAt")
        with tempfile.TemporaryDirectory() as directory:
            report = write_governed_handoff(handoff, Path(directory) / "handoff.json")
        self.assertEqual(report["status"], "PASS")
        self.assertFalse(report["executionAuthorized"])
        self.assertEqual(report["errors"], [])

    def test_export_digest_matches_agentflow_defaulted_artifact_arrays(self) -> None:
        handoff = self.handoff()
        agentflow_handoff = json.loads(json.dumps(handoff))
        agentflow_handoff["tasks"][0]["produces"] = []
        agentflow_handoff["tasks"][0]["consumes"] = []
        with tempfile.TemporaryDirectory() as directory:
            report = write_governed_handoff(handoff, Path(directory) / "handoff.json")
        self.assertEqual(report["sha256"], canonical_json_sha256(agentflow_handoff))

    def test_approved_handoff_without_current_repository_proof_cannot_authorize_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = write_governed_handoff(self.handoff(), Path(directory) / "handoff.json")

        self.assertFalse(report["executionAuthorized"], report)
        self.assertFalse(report["currencyVerified"], report)

    def test_repository_audit_passes_only_for_the_exact_governed_snapshot(self) -> None:
        verifier = getattr(agentflow_contracts, "audit_governed_handoff_repository", None)
        snapshot_builder = getattr(agentflow_contracts, "build_repository_authority_snapshot", None)
        self.assertIsNotNone(verifier, "repository-bound handoff verifier must exist")
        self.assertIsNotNone(snapshot_builder, "repository authority snapshot builder must exist")
        if verifier is None or snapshot_builder is None:
            return

        with tempfile.TemporaryDirectory() as directory:
            root = self._governed_repository(Path(directory))
            snapshot = snapshot_builder(root)
            handoff = self.handoff()
            handoff["repository"]["baseCommit"] = snapshot["baseCommit"]
            handoff["repository"]["snapshotSha256"] = snapshot["snapshotSha256"]
            handoff["authority"]["stateSha256"] = snapshot["authorityStateSha256"]
            handoff["authority"]["governanceReportSha256"] = snapshot["governanceReportSha256"]
            handoff["authority"]["sources"] = snapshot["sources"]

            audit = verifier(handoff, root)

        self.assertEqual(audit["status"], "PASS", audit)
        self.assertTrue(audit["currencyVerified"])

    def test_repository_audit_rejects_untracked_authority_added_after_handoff(self) -> None:
        verifier = getattr(agentflow_contracts, "audit_governed_handoff_repository", None)
        snapshot_builder = getattr(agentflow_contracts, "build_repository_authority_snapshot", None)
        self.assertIsNotNone(verifier, "repository-bound handoff verifier must exist")
        self.assertIsNotNone(snapshot_builder, "repository authority snapshot builder must exist")
        if verifier is None or snapshot_builder is None:
            return

        with tempfile.TemporaryDirectory() as directory:
            root = self._governed_repository(Path(directory))
            snapshot = snapshot_builder(root)
            handoff = self.handoff()
            handoff["repository"]["baseCommit"] = snapshot["baseCommit"]
            handoff["repository"]["snapshotSha256"] = snapshot["snapshotSha256"]
            handoff["authority"]["stateSha256"] = snapshot["authorityStateSha256"]
            handoff["authority"]["governanceReportSha256"] = snapshot["governanceReportSha256"]
            handoff["authority"]["sources"] = snapshot["sources"]
            path = root / "docs/product-intelligence/USER_JOURNEY_FUNNELS.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "# User Journey\n\nAuthority: canonical journeys\n\n"
                "`Intent -> Commitment -> Fulfillment`\n",
                encoding="utf-8",
            )

            audit = verifier(handoff, root)

        self.assertEqual(audit["status"], "FAIL", audit)
        self.assertFalse(audit["currencyVerified"])
        self.assertIn(
            "untracked critical authority candidates",
            " ".join(audit["errors"]).lower(),
        )

    def test_repository_audit_rejects_dirty_implementation_after_handoff(self) -> None:
        verifier = getattr(agentflow_contracts, "audit_governed_handoff_repository")
        snapshot_builder = getattr(agentflow_contracts, "build_repository_authority_snapshot")
        with tempfile.TemporaryDirectory() as directory:
            root = self._governed_repository(Path(directory))
            snapshot = snapshot_builder(root)
            handoff = self.handoff()
            handoff["repository"]["baseCommit"] = snapshot["baseCommit"]
            handoff["repository"]["snapshotSha256"] = snapshot["snapshotSha256"]
            handoff["authority"]["stateSha256"] = snapshot["authorityStateSha256"]
            handoff["authority"]["governanceReportSha256"] = snapshot["governanceReportSha256"]
            handoff["authority"]["sources"] = snapshot["sources"]
            (root / "src/app.py").write_text("VALUE = 2\n", encoding="utf-8")

            audit = verifier(handoff, root)

        self.assertEqual(audit["status"], "FAIL", audit)
        self.assertIn("worktree is not clean", " ".join(audit["errors"]).lower())

    def test_repository_audit_fails_cleanly_when_root_has_no_git_head(self) -> None:
        verifier = getattr(agentflow_contracts, "audit_governed_handoff_repository")
        with tempfile.TemporaryDirectory() as directory:
            audit = verifier(self.handoff(), Path(directory))

        self.assertEqual(audit["status"], "FAIL", audit)
        self.assertFalse(audit["currencyVerified"])
        self.assertIn("git", " ".join(audit["errors"]).lower())

    def test_cli_creates_and_validates_approved_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = self._governed_repository(base / "repo")
            snapshot_builder = getattr(agentflow_contracts, "build_repository_authority_snapshot")
            snapshot = snapshot_builder(root)
            handoff = self.handoff()
            handoff["repository"]["baseCommit"] = snapshot["baseCommit"]
            handoff["repository"]["snapshotSha256"] = snapshot["snapshotSha256"]
            handoff["authority"]["stateSha256"] = snapshot["authorityStateSha256"]
            handoff["authority"]["governanceReportSha256"] = snapshot["governanceReportSha256"]
            handoff["authority"]["sources"] = snapshot["sources"]
            source = base / "source.json"
            output = base / "handoff.json"
            source.write_text(json.dumps(handoff), encoding="utf-8")
            with redirect_stdout(StringIO()):
                create_code = cli_main([
                    "agentflow", "handoff-create", "--input", str(source),
                    "--output", str(output), "--repository", str(root), "--format", "json",
                ])
                validate_code = cli_main([
                    "agentflow", "handoff-validate", "--input", str(output),
                    "--repository", str(root), "--format", "json",
                ])
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

    def test_receipt_accepts_agentflow_defaulted_artifact_arrays(self) -> None:
        handoff = self.handoff()
        agentflow_handoff = json.loads(json.dumps(handoff))
        agentflow_handoff["tasks"][0]["produces"] = []
        agentflow_handoff["tasks"][0]["consumes"] = []
        receipt = {
            "schemaVersion": "1.0.0",
            "kind": "agentflow/build-receipt",
            "handoff": {
                "id": handoff["handoffId"],
                "sha256": canonical_json_sha256(agentflow_handoff),
            },
            "build": {
                "id": "build-1",
                "status": "completed",
                "baseCommit": "a" * 40,
                "integrationCommit": "c" * 40,
            },
            "tasks": [{
                "id": "AF-001",
                "status": "integrated",
                "resultCommit": "d" * 40,
                "integrationCommit": "c" * 40,
                "changedFiles": ["src/contracts/index.ts"],
                "validation": [],
            }],
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

    def _governed_repository(self, root: Path) -> Path:
        files = {
            "AGENTS.md": "# Instructions\n",
            "docs/product/product-vision.md": "# Product Vision\n\nThe product serves operators.\n",
            "docs/product/platform-specification.md": "# Requirements\n\nStatus: active\n",
            "docs/architecture/mvp-golden-path.md": (
                "# Product Journey\n\nAuthority: canonical journeys\n\n"
                "`Intent -> Decision -> Completion`\n\nProof: `e2e/product-journey.spec.ts`\n"
            ),
            "docs/architecture/adr/0001-architecture.md": "# ADR\n\nStatus: accepted\n",
            "docs/backlog-now.md": (
                "# Backlog\n\n### TRUST-001: Preserve the journey\n\n"
                "- Status: ACTIVE\n- Outcome: operators finish reliably.\n"
                "- Success signal: the journey proof passes.\n"
                "- Evidence or assumption: governed source evidence.\n"
            ),
            "e2e/product-journey.spec.ts": "// journey proof\n",
            "src/app.py": "VALUE = 1\n",
            "package.json": json.dumps({
                "scripts": {"test:e2e:product": "playwright test e2e/product-journey.spec.ts"}
            }),
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(
            [
                "git", "-c", "user.name=Proofloom Tests", "-c",
                "user.email=proofloom-tests@example.invalid", "commit", "-qm", "fixture",
            ],
            cwd=root,
            check=True,
        )
        apply_governance_convergence(root)
        subprocess.run(["git", "add", ".dev/governance"], cwd=root, check=True)
        subprocess.run(
            [
                "git", "-c", "user.name=Proofloom Tests", "-c",
                "user.email=proofloom-tests@example.invalid", "commit", "-qm", "governance",
            ],
            cwd=root,
            check=True,
        )
        return root


if __name__ == "__main__":
    unittest.main()
