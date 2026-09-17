from __future__ import annotations

import unittest

from design_intelligence.agentflow_contracts import canonical_json_sha256
from design_intelligence.traffic_control_escalation import create_escalation_proposal, record_escalation_resolution


def _handoff(identifier: str = "DI-1") -> dict:
    return {
        "schemaVersion": "2.0.0", "kind": "design-intelligence/governed-task-handoff", "handoffId": identifier,
        "createdAt": "2026-09-17T12:00:00Z", "repository": {"baseCommit": "a" * 40, "snapshotSha256": "b" * 64, "worktreeState": "clean"},
        "objective": "Resolve a bounded structural concern through reviewed authority.",
        "authority": {"status": "APPROVED", "approvedBy": "owner", "approvedAt": "2026-09-17T12:01:00Z", "stateSha256": "c" * 64, "governanceReportSha256": "d" * 64, "sources": [{"path": "AGENTS.md", "sha256": "e" * 64}]},
        "tasks": [{"id": "AF-001", "title": "Task", "description": "Execute approved structure.", "estimateHours": 1, "dependsOn": [], "owns": ["src/"], "acceptanceCriteria": ["Passes"], "validate": ["npm test"], "produces": [], "consumes": []}],
        "proof": {"requiredEvidence": ["tests"], "claimBoundary": "Local only."},
    }


def _receipt(handoff: dict) -> dict:
    record = {
        "schema": "traffic-control/governor-decision-record@1", "recordedAt": "2026-09-17T12:10:00Z",
        "contractHash": canonical_json_sha256(handoff), "observationHash": "f" * 64, "previousRecordHash": None,
        "policyVersion": "governor.v1",
        "decision": {"policyVersion": "governor.v1", "action": "PROPOSE_REPLAN", "ruleId": "repeated-no-progress-failure", "authorityEffect": "PROPOSAL_ONLY", "requiresApproval": True, "signals": {"failureFingerprint": "1" * 64}},
    }
    record["recordHash"] = canonical_json_sha256(record)
    return {"handoff": {"id": handoff["handoffId"], "sha256": canonical_json_sha256(handoff)}, "build": {"id": "build-1"}, "evidence": {"events": [{"type": "governor.decision", "sequence": 8, "payload": record}]}}


class TrafficControlEscalationTests(unittest.TestCase):
    def test_proposal_remains_non_executable_until_external_selection(self) -> None:
        handoff = _handoff()
        proposal = create_escalation_proposal(_receipt(handoff), handoff, alternatives=[{"id": "A", "summary": "Repair in place"}, {"id": "B", "summary": "Move the authority boundary"}])
        self.assertEqual(proposal["status"], "REVIEW_REQUIRED")
        self.assertFalse(proposal["mayExecute"])
        self.assertEqual(proposal["sourceHandoff"]["sha256"], canonical_json_sha256(handoff))
        self.assertRegex(proposal["proposalSha256"], r"^[0-9a-f]{64}$")

    def test_approval_requires_authorized_superseding_handoff(self) -> None:
        handoff = _handoff()
        proposal = create_escalation_proposal(_receipt(handoff), handoff, alternatives=[{"id": "A", "summary": "Repair"}, {"id": "B", "summary": "Move boundary"}])
        replacement = _handoff("DI-2")
        resolution = record_escalation_resolution(proposal, {"status": "APPROVED", "authorityClass": "HUMAN_OR_REPOSITORY", "selectedAlternativeId": "B", "newHandoff": replacement, "recordedAt": "2026-09-17T13:00:00Z"})
        self.assertTrue(resolution["mayExecute"])
        self.assertEqual(resolution["supersession"]["priorHandoffId"], "DI-1")
        self.assertEqual(resolution["supersession"]["newHandoffId"], "DI-2")

    def test_advisory_output_cannot_approve_itself(self) -> None:
        proposal = create_escalation_proposal(_receipt(_handoff()), _handoff(), alternatives=[{"id": "A", "summary": "Repair"}, {"id": "B", "summary": "Move boundary"}])
        with self.assertRaisesRegex(ValueError, "human or repository"):
            record_escalation_resolution(proposal, {"status": "APPROVED", "authorityClass": "DECISION_INTELLIGENCE", "selectedAlternativeId": "A", "newHandoff": _handoff("DI-2"), "recordedAt": "2026-09-17T13:00:00Z"})

    def test_rejection_revision_and_cancellation_are_durable_non_execution_records(self) -> None:
        proposal = create_escalation_proposal(_receipt(_handoff()), _handoff(), alternatives=[{"id": "A", "summary": "Repair"}, {"id": "B", "summary": "Move boundary"}])
        prior = None
        for status in ("REJECTED", "REVISION_REQUESTED", "CANCELLED"):
            record = record_escalation_resolution(proposal, {"status": status, "authorityClass": "HUMAN_OR_REPOSITORY", "reason": status.lower(), "recordedAt": "2026-09-17T13:00:00Z", "previousRecordHash": prior})
            self.assertFalse(record["mayExecute"])
            self.assertEqual(record["previousRecordHash"], prior)
            prior = record["recordHash"]


if __name__ == "__main__":
    unittest.main()
