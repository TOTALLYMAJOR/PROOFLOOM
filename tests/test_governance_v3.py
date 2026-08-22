from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from design_intelligence.baselines import (
    audit_baseline_review_request,
    create_baseline_review_request,
)
from design_intelligence.memory import append_decision, append_outcome, initialize_memory
from design_intelligence.review_lifecycle import (
    audit_baseline_review_receipt,
    create_baseline_review_receipt,
    evaluate_baseline_review_lifecycle,
    load_review_policy,
    preflight_baseline_promotion,
)
from design_intelligence.self_audit import run_self_audit


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class GovernanceV3Tests(unittest.TestCase):
    def test_human_approval_receipt_binds_evidence_without_promoting_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("fixture", encoding="utf-8")
            initialize_memory(root)
            qa_path, model_path, candidate_root = self._write_evidence(root)
            request_path = root / "artifacts/design/baseline-requests/surface.json"
            request = create_baseline_review_request(
                root,
                "surface",
                "Test Product",
                qa_path,
                model_path,
                candidate_root,
                "agent:test",
                request_path,
            )
            self._set_requested_at(request, request_path)
            self._accept_design_decision(root)
            visual_path = self._write_human_evidence(root, request["id"], "visual-acceptance")
            semantic_path = self._write_human_evidence(root, request["id"], "semantic-accessibility")
            receipt_path = root / "artifacts/design/baseline-decisions/approve-surface.json"
            manifest_path = root / ".design/baselines/manifest.json"
            manifest_before = manifest_path.read_bytes()

            receipt = create_baseline_review_receipt(
                root,
                request_path,
                {
                    "decision": "APPROVE",
                    "authorizedBy": "human:product-owner",
                    "reason": "The rendered surface and semantics are accepted for baseline review.",
                    "decisionMemoryId": "DL-V3-REVIEW-001",
                    "visualAcceptanceEvidence": visual_path.relative_to(root).as_posix(),
                    "semanticAccessibilityEvidence": semantic_path.relative_to(root).as_posix(),
                },
                receipt_path,
                decided_at=datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc),
            )

            self.assertEqual(receipt["decision"], "APPROVE")
            self.assertEqual(receipt["requestId"], request["id"])
            self.assertFalse(receipt["baselineMutationPerformed"])
            self.assertEqual(manifest_path.read_bytes(), manifest_before)
            self.assertEqual(audit_baseline_review_receipt(root, receipt_path)["status"], "PASS")
            with self.assertRaisesRegex(ValueError, "append-only"):
                create_baseline_review_receipt(
                    root,
                    request_path,
                    {
                        "decision": "APPROVE",
                        "authorizedBy": "human:product-owner",
                        "reason": "Duplicate write must be denied.",
                        "decisionMemoryId": "DL-V3-REVIEW-001",
                        "visualAcceptanceEvidence": visual_path.relative_to(root).as_posix(),
                        "semanticAccessibilityEvidence": semantic_path.relative_to(root).as_posix(),
                    },
                    receipt_path,
                )
            visual_path.write_text(json.dumps({"status": "CHANGED"}), encoding="utf-8")
            tampered = audit_baseline_review_receipt(root, receipt_path)
            self.assertEqual(tampered["status"], "FAIL")
            self.assertTrue(any("hash mismatch" in error for error in tampered["errors"]))

    def test_agent_identity_cannot_record_human_review_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qa_path, model_path, candidate_root = self._write_evidence(root)
            request_path = root / "artifacts/design/baseline-requests/surface.json"
            create_baseline_review_request(
                root,
                "surface",
                "Test Product",
                qa_path,
                model_path,
                candidate_root,
                "agent:test",
                request_path,
            )
            receipt_path = root / "artifacts/design/baseline-decisions/reject-surface.json"

            with self.assertRaisesRegex(ValueError, "human authority"):
                create_baseline_review_receipt(
                    root,
                    request_path,
                    {
                        "decision": "REJECT",
                        "authorizedBy": "agent:codex",
                        "reason": "An agent cannot impersonate a human reviewer.",
                    },
                    receipt_path,
                )
            self.assertFalse(receipt_path.exists())

    def test_human_can_defer_blocked_request_without_granting_promotion_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qa_path, model_path, candidate_root = self._write_evidence(
                root,
                qa_status="FAIL",
                serious_violations=6,
                model_verdict="FAIL",
                model_severity="P1",
            )
            request_path = root / "artifacts/design/baseline-requests/surface.json"
            request = create_baseline_review_request(
                root,
                "surface",
                "Test Product",
                qa_path,
                model_path,
                candidate_root,
                "agent:test",
                request_path,
            )
            receipt_path = root / "artifacts/design/baseline-decisions/defer-surface.json"

            receipt = create_baseline_review_receipt(
                root,
                request_path,
                {
                    "decision": "DEFER",
                    "authorizedBy": "human:product-owner",
                    "reason": "Keep repair on hold until product scope is reopened.",
                    "reviewAfter": "2026-09-04T12:00:00Z",
                },
                receipt_path,
                decided_at=datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc),
            )

            self.assertEqual(receipt["requestId"], request["id"])
            self.assertEqual(receipt["decision"], "DEFER")
            self.assertFalse(receipt["promotionPerformed"])
            self.assertNotIn("decisionMemoryId", receipt)
            self.assertEqual(audit_baseline_review_receipt(root, receipt_path)["status"], "PASS")

    def test_promotion_preflight_is_ready_only_while_approval_receipt_is_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("fixture", encoding="utf-8")
            initialize_memory(root)
            qa_path, model_path, candidate_root = self._write_evidence(root)
            request_path = root / "artifacts/design/baseline-requests/surface.json"
            request = create_baseline_review_request(
                root,
                "surface",
                "Test Product",
                qa_path,
                model_path,
                candidate_root,
                "agent:test",
                request_path,
            )
            self._set_requested_at(request, request_path)
            self._accept_design_decision(root)
            visual_path = self._write_human_evidence(root, request["id"], "visual-acceptance")
            semantic_path = self._write_human_evidence(root, request["id"], "semantic-accessibility")
            receipt_path = root / "artifacts/design/baseline-decisions/approve-surface.json"
            create_baseline_review_receipt(
                root,
                request_path,
                {
                    "decision": "APPROVE",
                    "authorizedBy": "human:product-owner",
                    "reason": "Approve the bound candidate for a limited promotion window.",
                    "decisionMemoryId": "DL-V3-REVIEW-001",
                    "visualAcceptanceEvidence": visual_path.relative_to(root).as_posix(),
                    "semanticAccessibilityEvidence": semantic_path.relative_to(root).as_posix(),
                    "validForDays": 2,
                },
                receipt_path,
                decided_at=datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc),
            )
            manifest_path = root / ".design/baselines/manifest.json"
            manifest_before = manifest_path.read_bytes()

            ready = preflight_baseline_promotion(
                root,
                receipt_path,
                as_of=datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc),
            )
            expired = preflight_baseline_promotion(
                root,
                receipt_path,
                as_of=datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc),
            )

            self.assertEqual(ready["status"], "READY")
            self.assertEqual(ready["scenarioId"], "surface")
            self.assertEqual(ready["approval"]["decisionId"], "DL-V3-REVIEW-001")
            self.assertFalse(ready["baselineMutationPerformed"])
            self.assertEqual(expired["status"], "BLOCKED")
            self.assertTrue(any("expired" in error.lower() for error in expired["errors"]))
            tampered_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            tampered_receipt["requestEvidence"]["path"] = "../outside-request.json"
            receipt_path.write_text(json.dumps(tampered_receipt), encoding="utf-8")
            malformed = preflight_baseline_promotion(root, receipt_path)
            self.assertEqual(malformed["status"], "BLOCKED")
            self.assertTrue(malformed["errors"])
            self.assertEqual(manifest_path.read_bytes(), manifest_before)

    def test_later_human_receipt_supersedes_prior_approval_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("fixture", encoding="utf-8")
            initialize_memory(root)
            qa_path, model_path, candidate_root = self._write_evidence(root)
            request_path = root / "artifacts/design/baseline-requests/surface.json"
            request = create_baseline_review_request(
                root,
                "surface",
                "Test Product",
                qa_path,
                model_path,
                candidate_root,
                "agent:test",
                request_path,
            )
            self._set_requested_at(request, request_path)
            self._accept_design_decision(root)
            visual_path = self._write_human_evidence(root, request["id"], "visual-acceptance")
            semantic_path = self._write_human_evidence(root, request["id"], "semantic-accessibility")
            decisions_root = root / "artifacts/design/baseline-decisions"
            approval_path = decisions_root / "approve-surface.json"
            approval = create_baseline_review_receipt(
                root,
                request_path,
                {
                    "decision": "APPROVE",
                    "authorizedBy": "human:product-owner",
                    "reason": "Initial time-bounded approval.",
                    "decisionMemoryId": "DL-V3-REVIEW-001",
                    "visualAcceptanceEvidence": visual_path.relative_to(root).as_posix(),
                    "semanticAccessibilityEvidence": semantic_path.relative_to(root).as_posix(),
                },
                approval_path,
                decided_at=datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc),
            )
            with self.assertRaisesRegex(ValueError, "must supersede"):
                create_baseline_review_receipt(
                    root,
                    request_path,
                    {
                        "decision": "REJECT",
                        "authorizedBy": "human:product-owner",
                        "reason": "A competing receipt cannot bypass supersession.",
                    },
                    decisions_root / "conflicting-reject.json",
                    decided_at=datetime(2026, 8, 21, 12, 30, tzinfo=timezone.utc),
                )
            defer_path = decisions_root / "defer-surface.json"
            defer = create_baseline_review_receipt(
                root,
                request_path,
                {
                    "decision": "DEFER",
                    "authorizedBy": "human:product-owner",
                    "reason": "New evidence requires another review.",
                    "reviewAfter": "2026-09-04T13:00:00Z",
                    "supersedes": approval["id"],
                },
                defer_path,
                decided_at=datetime(2026, 8, 21, 13, 0, tzinfo=timezone.utc),
            )

            preflight = preflight_baseline_promotion(
                root,
                approval_path,
                as_of=datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc),
            )

            self.assertEqual(defer["supersedes"], approval["id"])
            self.assertEqual(audit_baseline_review_receipt(root, defer_path)["status"], "PASS")
            self.assertEqual(preflight["status"], "BLOCKED")
            self.assertTrue(any("superseded" in error.lower() for error in preflight["errors"]))

    def test_reviewable_request_becomes_stale_without_mutating_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qa_path, model_path, candidate_root = self._write_evidence(root)
            request_path = root / "artifacts/design/baseline-requests/surface.json"
            request = create_baseline_review_request(
                root,
                "surface",
                "Test Product",
                qa_path,
                model_path,
                candidate_root,
                "agent:test",
                request_path,
            )
            request["requestedAt"] = "2026-08-01T12:00:00Z"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            request_before = request_path.read_bytes()

            lifecycle = evaluate_baseline_review_lifecycle(
                root,
                as_of=datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc),
            )

            self.assertEqual(lifecycle["status"], "PASS")
            self.assertEqual(lifecycle["requests"][0]["state"], "STALE")
            self.assertEqual(lifecycle["counts"]["STALE"], 1)
            self.assertEqual(request_path.read_bytes(), request_before)

    def test_stale_review_request_cannot_receive_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("fixture", encoding="utf-8")
            initialize_memory(root)
            qa_path, model_path, candidate_root = self._write_evidence(root)
            request_path = root / "artifacts/design/baseline-requests/surface.json"
            request = create_baseline_review_request(
                root,
                "surface",
                "Test Product",
                qa_path,
                model_path,
                candidate_root,
                "agent:test",
                request_path,
            )
            request["requestedAt"] = "2026-08-01T12:00:00Z"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            self._accept_design_decision(root)
            visual_path = self._write_human_evidence(root, request["id"], "visual-acceptance")
            semantic_path = self._write_human_evidence(root, request["id"], "semantic-accessibility")

            with self.assertRaisesRegex(ValueError, "stale"):
                create_baseline_review_receipt(
                    root,
                    request_path,
                    {
                        "decision": "APPROVE",
                        "authorizedBy": "human:product-owner",
                        "reason": "Old evidence must be refreshed before approval.",
                        "decisionMemoryId": "DL-V3-REVIEW-001",
                        "visualAcceptanceEvidence": visual_path.relative_to(root).as_posix(),
                        "semanticAccessibilityEvidence": semantic_path.relative_to(root).as_posix(),
                    },
                    root / "artifacts/design/baseline-decisions/approve-stale.json",
                    decided_at=datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc),
                )

    def test_review_policy_can_tighten_but_cannot_extend_governance_windows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy_path = root / ".design/baselines/review-policy.json"
            policy_path.parent.mkdir(parents=True)
            policy_path.write_text(json.dumps({
                "schemaVersion": 1,
                "maxRequestAgeDays": 7,
                "maxApprovalAgeDays": 3,
                "maxDeferAgeDays": 14,
                "requireHumanAuthority": True,
                "requireBoundVisualAcceptance": True,
                "requireBoundSemanticAccessibility": True,
            }), encoding="utf-8")
            self.assertEqual(load_review_policy(root)["maxApprovalAgeDays"], 3)

            policy_path.write_text(json.dumps({
                "schemaVersion": 1,
                "maxRequestAgeDays": 60,
                "maxApprovalAgeDays": 30,
                "maxDeferAgeDays": 90,
                "requireHumanAuthority": False,
                "requireBoundVisualAcceptance": False,
                "requireBoundSemanticAccessibility": False,
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "weakens protected governance"):
                load_review_policy(root)

    def test_memory_initialization_installs_receipt_schema_and_review_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("fixture", encoding="utf-8")

            initialize_memory(root)

            schema = root / ".design/memory/schemas/baseline-review-receipt.schema.json"
            policy = root / ".design/baselines/review-policy.json"
            self.assertTrue(schema.is_file())
            self.assertTrue(policy.is_file())
            self.assertEqual(load_review_policy(root)["maxRequestAgeDays"], 14)

    def test_self_audit_reports_weakened_review_policy_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("fixture", encoding="utf-8")
            initialize_memory(root)
            policy_path = root / ".design/baselines/review-policy.json"
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy["maxApprovalAgeDays"] = 30
            policy_path.write_text(json.dumps(policy), encoding="utf-8")

            report = run_self_audit(root)

            self.assertEqual(report["status"], "FAIL")
            self.assertEqual(report["checks"]["baselineReviewPolicy"]["status"], "FAIL")
            self.assertEqual(report["checks"]["baselineReviewLifecycle"]["status"], "FAIL")

    def test_reviewable_request_binds_evidence_without_mutating_baselines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qa_path, model_path, candidate_root = self._write_evidence(root)
            output = root / "artifacts/design/baseline-requests/surface.json"

            request = create_baseline_review_request(
                root,
                "surface",
                "Test Product",
                qa_path,
                model_path,
                candidate_root,
                "agent:test",
                output,
            )

            self.assertEqual(request["status"], "REVIEWABLE")
            self.assertFalse(request["baselineMutationPerformed"])
            self.assertEqual(request["promotionAuthority"], "human-required")
            self.assertEqual(len(request["candidates"]), 5)
            self.assertFalse((root / ".design/baselines").exists())
            self.assertEqual(audit_baseline_review_request(root, output)["status"], "PASS")

            first_candidate = next(iter(request["candidates"].values()))
            (root / first_candidate["path"]).write_bytes(b"changed")
            audit = audit_baseline_review_request(root, output)
            self.assertEqual(audit["status"], "FAIL")
            self.assertTrue(any("hash mismatch" in error for error in audit["errors"]))

    def test_failed_qa_and_model_review_create_blocked_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qa_path, model_path, candidate_root = self._write_evidence(
                root,
                qa_status="FAIL",
                serious_violations=6,
                model_verdict="FAIL",
                model_severity="P1",
            )
            output = root / "artifacts/design/baseline-requests/surface.json"

            request = create_baseline_review_request(
                root,
                "surface",
                "Test Product",
                qa_path,
                model_path,
                candidate_root,
                "agent:test",
                output,
            )

            self.assertEqual(request["status"], "BLOCKED")
            self.assertTrue(any("serious accessibility" in blocker for blocker in request["blockers"]))
            self.assertTrue(any("model visual review failed" in blocker for blocker in request["blockers"]))
            self.assertEqual(audit_baseline_review_request(root, output)["status"], "PASS")
            self.assertFalse((root / ".design/baselines").exists())

            request["status"] = "REVIEWABLE"
            request["blockers"] = []
            output.write_text(json.dumps(request), encoding="utf-8")
            tampered = audit_baseline_review_request(root, output)
            self.assertEqual(tampered["status"], "FAIL")
            self.assertTrue(any("bound evidence" in error for error in tampered["errors"]))

    def test_remote_ci_is_read_only_and_tiered(self) -> None:
        workflow = (REPOSITORY_ROOT / ".github/workflows/design-ci.yml").read_text(encoding="utf-8")

        self.assertIn("pull_request:", workflow)
        self.assertIn("quick:", workflow)
        self.assertIn("standard:", workflow)
        self.assertIn("full:", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("actions/checkout@v7", workflow)
        self.assertIn("actions/setup-python@v7", workflow)
        self.assertIn("actions/setup-node@v7", workflow)
        self.assertIn("actions/upload-artifact@v7", workflow)
        self.assertNotIn("pull_request_target", workflow)
        self.assertNotIn("baseline promote", workflow)
        self.assertNotIn("repair --apply", workflow)
        self.assertIn("artifacts/design/screenshots/design-department-surface/", workflow)
        self.assertIn("artifacts/design/diffs/design-department-surface/", workflow)

        fixture_css = (REPOSITORY_ROOT / "tests/fixtures/visual-surface/surface.css").read_text(encoding="utf-8")
        self.assertIn('font-family: "DejaVu Serif", serif;', fixture_css)
        self.assertIn('font-family: "DejaVu Sans Mono", monospace;', fixture_css)

    def _write_evidence(
        self,
        root: Path,
        *,
        qa_status: str = "PASS",
        serious_violations: int = 0,
        model_verdict: str = "WARN",
        model_severity: str = "P2",
    ) -> tuple[Path, Path, Path]:
        thresholds = root / ".design/quality/thresholds.json"
        thresholds.parent.mkdir(parents=True, exist_ok=True)
        thresholds.write_text(json.dumps({"requiredViewportCount": 5}), encoding="utf-8")
        candidate_root = root / "artifacts/design/screenshots/surface"
        viewports = []
        for index in range(5):
            viewport_id = f"viewport-{index + 1}"
            screenshot = candidate_root / viewport_id / "current.png"
            screenshot.parent.mkdir(parents=True)
            screenshot.write_bytes(f"png-{index}".encode())
            viewports.append({
                "id": viewport_id,
                "status": "PASS" if qa_status == "PASS" else ("FAIL" if index == 0 else "PASS"),
                "artifacts": {"currentScreenshot": screenshot.relative_to(root).as_posix()},
            })
        qa = {
            "surface": "Test surface",
            "status": qa_status,
            "sourceRevision": {
                "repository": "test",
                "branch": "test",
                "commitSha": "abcdef1234567890",
            },
            "viewports": viewports,
            "totals": {
                "criticalAccessibilityViolations": 0,
                "seriousAccessibilityViolations": serious_violations,
                "containmentFailures": 0,
                "domAssertionsPassed": 25,
                "domAssertionsTotal": 25,
                "contractAssertionsPassed": 25,
                "contractAssertionsTotal": 25,
            },
        }
        model = {
            "surface": "Test surface",
            "verdict": model_verdict,
            "severity": model_severity,
        }
        qa_path = root / "artifacts/design/reports/surface/qa-report.json"
        model_path = root / "artifacts/design/reports/surface/model-visual-review.json"
        qa_path.parent.mkdir(parents=True)
        qa_path.write_text(json.dumps(qa), encoding="utf-8")
        model_path.write_text(json.dumps(model), encoding="utf-8")
        return qa_path, model_path, candidate_root

    def _accept_design_decision(self, root: Path) -> None:
        proposal = {
            "id": "DL-V3-REVIEW-001",
            "status": "proposed",
            "authorityLevel": "product",
            "product": "Test Product",
            "decision": "Permit a human-reviewed baseline candidate.",
            "problem": "Candidate evidence requires durable authority.",
            "evidence": ["baseline review request"],
            "alternatives": ["leave candidate unapproved"],
            "reason": "Bind approval to institutional memory.",
            "affectedComponents": ["Test surface"],
            "createdAt": "2026-08-21T10:00:00Z",
        }
        append_decision(root, proposal)
        append_outcome(root, {
            "id": "DO-V3-REVIEW-001",
            "decisionId": proposal["id"],
            "result": "accepted",
            "reason": "Human review evidence is available.",
            "evidence": ["visual acceptance", "semantic accessibility"],
            "lesson": "Promotion remains separate from approval.",
            "recordedAt": "2026-08-21T11:00:00Z",
        })
        append_decision(root, {
            **proposal,
            "status": "accepted",
            "revision": 2,
            "promotion": {
                "authorizedBy": "human:product-owner",
                "outcomeId": "DO-V3-REVIEW-001",
                "validationEvidence": ["human review receipt"],
            },
        })

    def _set_requested_at(
        self,
        request: dict[str, object],
        request_path: Path,
    ) -> None:
        request["requestedAt"] = "2026-08-21T10:00:00Z"
        request_path.write_text(json.dumps(request), encoding="utf-8")

    def _write_human_evidence(self, root: Path, request_id: str, scope: str) -> Path:
        path = root / f"artifacts/design/human-review/{scope}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "requestId": request_id,
            "status": "PASS",
            "reviewedBy": "human:product-owner",
            "reviewedAt": "2026-08-21T11:30:00Z",
            "scope": scope,
        }), encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
