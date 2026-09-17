from __future__ import annotations

from copy import deepcopy
import unittest

from design_intelligence.agentflow_contracts import canonical_json_sha256
from design_intelligence.traffic_control_audit import audit_traffic_control_receipt


def _handoff() -> dict:
    return {
        "schemaVersion": "2.0.0",
        "kind": "design-intelligence/governed-task-handoff",
        "handoffId": "DI-TCP-001",
        "createdAt": "2026-09-17T12:00:00Z",
        "repository": {"baseCommit": "a" * 40, "snapshotSha256": "b" * 64, "worktreeState": "clean"},
        "objective": "Complete a governed execution with independently auditable proof.",
        "authority": {
            "status": "APPROVED", "approvedBy": "owner", "approvedAt": "2026-09-17T12:01:00Z",
            "stateSha256": "c" * 64, "governanceReportSha256": "d" * 64,
            "sources": [{"path": "AGENTS.md", "sha256": "e" * 64}],
        },
        "tasks": [{
            "id": "AF-001", "title": "Implement", "description": "Implement the governed slice.", "estimateHours": 1,
            "dependsOn": [], "owns": ["src/"], "acceptanceCriteria": ["Tests pass"], "validate": ["npm test"],
            "produces": [], "consumes": [],
        }],
        "proof": {"requiredEvidence": ["focused-tests"], "claimBoundary": "Local execution and integration proof only."},
    }


def _receipt(handoff: dict) -> dict:
    handoff_hash = canonical_json_sha256(handoff)
    observation_hash = "f" * 64
    record = {
        "schema": "traffic-control/governor-decision-record@1",
        "recordedAt": "2026-09-17T12:10:00Z",
        "contractHash": handoff_hash,
        "observationHash": observation_hash,
        "previousRecordHash": None,
        "policyVersion": "governor.v1",
        "decision": {
            "policyVersion": "governor.v1", "action": "CONTINUE", "ruleId": "entitled-to-continue",
            "authorityEffect": "NONE", "requiresApproval": False, "signals": {},
        },
    }
    record["recordHash"] = canonical_json_sha256(record)
    authority = {
        "approvalAuthority": "HUMAN_OR_REPOSITORY", "handoffId": handoff["handoffId"], "handoffSha256": handoff_hash,
        "repositoryId": None, "baseCommit": handoff["repository"]["baseCommit"],
        "snapshotSha256": handoff["repository"]["snapshotSha256"], "worktreeState": "clean",
        "authorityStateSha256": handoff["authority"]["stateSha256"],
        "governanceReportSha256": handoff["authority"]["governanceReportSha256"],
        "authoritySources": handoff["authority"]["sources"],
    }
    return {
        "schemaVersion": "1.0.0", "kind": "agentflow/build-receipt",
        "handoff": {"id": handoff["handoffId"], "sha256": handoff_hash},
        "build": {"id": "build-1", "status": "completed", "baseCommit": "1" * 40, "governedBaseCommit": handoff["repository"]["baseCommit"], "integrationCommit": "2" * 40},
        "tasks": [{
            "id": "AF-001", "status": "integrated", "resultCommit": "3" * 40, "integrationCommit": "4" * 40,
            "changedFiles": ["src/index.ts"],
            "validation": [{"command": "npm test", "status": "passed", "exitCode": 0}],
        }],
        "evidence": {
            "events": [
                {"type": "evidence.recorded", "payload": {"satisfied": ["focused-tests"]}},
                {"type": "governor.decision", "payload": {**record, "authorityObservation": authority}},
            ],
            "artifacts": [], "approvals": [],
        },
        "proofBoundary": handoff["proof"]["claimBoundary"], "generatedAt": "2026-09-17T12:11:00Z",
    }


def test_audits_exact_governed_completion() -> None:
    handoff = _handoff()
    result = audit_traffic_control_receipt(_receipt(handoff), handoff)
    assert result["status"] == "PASS"
    assert result["executionComplete"] is True
    assert result["governorVerified"] is True
    assert result["claim"] == "AgentFlow local execution and integration evidence verified."


def test_rejects_unauthorized_changed_file() -> None:
    handoff = _handoff()
    receipt = _receipt(handoff)
    receipt["tasks"][0]["changedFiles"] = ["outside/escape.ts"]
    result = audit_traffic_control_receipt(receipt, handoff)
    assert result["status"] == "FAIL"
    assert any("outside governed ownership" in error for error in result["errors"])


def test_rejects_missing_task_and_failed_validation() -> None:
    handoff = _handoff()
    missing = _receipt(handoff)
    missing["tasks"][0]["id"] = "AF-OTHER"
    missing_result = audit_traffic_control_receipt(missing, handoff)
    assert missing_result["status"] == "FAIL"
    assert any("task set" in error for error in missing_result["errors"])

    failed = _receipt(handoff)
    failed["tasks"][0]["validation"][0]["status"] = "failed"
    failed["tasks"][0]["validation"][0]["exitCode"] = 1
    failed_result = audit_traffic_control_receipt(failed, handoff)
    assert failed_result["status"] == "FAIL"
    assert any("validation" in error for error in failed_result["errors"])


def test_rejects_mutated_decision_record_and_non_continue_completion() -> None:
    handoff = _handoff()
    receipt = _receipt(handoff)
    receipt["evidence"]["events"][-1]["payload"]["decision"]["action"] = "PAUSE_FOR_REVIEW"
    result = audit_traffic_control_receipt(receipt, handoff)
    assert result["status"] == "FAIL"
    assert any("record hash" in error for error in result["errors"])
    assert any("CONTINUE" in error for error in result["errors"])


def test_rejects_substituted_contract_authority_and_proof_boundary() -> None:
    handoff = _handoff()
    receipt = _receipt(handoff)
    receipt["handoff"]["sha256"] = "0" * 64
    receipt["proofBoundary"] = "Production proven."
    receipt["evidence"]["events"][-1]["payload"]["authorityObservation"]["snapshotSha256"] = "9" * 64
    result = audit_traffic_control_receipt(receipt, handoff)
    assert result["status"] == "FAIL"
    assert any("handoff sha256" in error for error in result["errors"])
    assert any("proof boundary" in error for error in result["errors"])
    assert any("snapshot" in error for error in result["errors"])


def test_rejects_missing_required_evidence() -> None:
    handoff = _handoff()
    receipt = deepcopy(_receipt(handoff))
    receipt["evidence"]["events"] = receipt["evidence"]["events"][1:]
    result = audit_traffic_control_receipt(receipt, handoff)
    assert result["status"] == "FAIL"
    assert any("required evidence" in error for error in result["errors"])


def load_tests(loader: unittest.TestLoader, tests: unittest.TestSuite, pattern: str | None) -> unittest.TestSuite:
    del loader, tests, pattern
    return unittest.TestSuite(
        unittest.FunctionTestCase(function)
        for function in (
            test_audits_exact_governed_completion,
            test_rejects_unauthorized_changed_file,
            test_rejects_missing_task_and_failed_validation,
            test_rejects_mutated_decision_record_and_non_continue_completion,
            test_rejects_substituted_contract_authority_and_proof_boundary,
            test_rejects_missing_required_evidence,
        )
    )
