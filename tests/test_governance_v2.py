from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from design_intelligence.baselines import audit_baselines, promote_baseline
from design_intelligence.contracts import create_contract, validate_contract
from design_intelligence.memory import append_decision, append_outcome, initialize_memory
from design_intelligence.quality import audit_thresholds, load_thresholds, score_quality
from design_intelligence.registry import build_component_registry
from design_intelligence.repair import apply_repair_plan


FIXTURES = Path(__file__).parent / "fixtures"


class GovernanceV2Tests(unittest.TestCase):
    def test_contract_rejects_missing_measurable_criteria(self) -> None:
        errors = validate_contract({"taskId": "TEST"})
        self.assertIn("Missing required field: acceptanceCriteria", errors)

    def test_contract_creation_preserves_actor_task_fields(self) -> None:
        payload = {
            "taskId": "TEST-1", "product": "Test", "surface": "Surface", "actor": "operator",
            "object": "record", "goal": "finish task", "decision": "proceed", "state": "ready",
            "blocker": "none", "authority": "owner", "primaryAction": "Continue",
            "acceptanceCriteria": ["primary action is visible"],
        }
        contract = create_contract(payload)
        self.assertEqual(contract["actor"], "operator")
        self.assertEqual(contract["informationPriority"]["primary"], [])

    def test_quality_is_deterministic_and_thresholds_cannot_be_weakened(self) -> None:
        thresholds = load_thresholds()
        qa = {
            "repairIterations": 0,
            "viewports": [
                {"visual": {"status": "PASS", "governed": True, "diffRatio": 0}}
                for _ in range(5)
            ],
            "totals": {
                "criticalAccessibilityViolations": 0, "seriousAccessibilityViolations": 0,
                "moderateAccessibilityViolations": 0, "containmentFailures": 0,
                "domAssertionsPassed": 10, "domAssertionsTotal": 10,
                "contractAssertionsPassed": 10, "contractAssertionsTotal": 10,
            },
        }
        report = score_quality(qa, thresholds)
        self.assertEqual(report.score, 100)
        self.assertEqual(report.drift_score, 0)
        self.assertTrue(report.deterministic_only)
        self.assertTrue(audit_thresholds({**thresholds, "qualityPassScore": 80}))
        self.assertTrue(audit_thresholds({**thresholds, "maxPixelDiffRatio": 0.1}))

    def test_repair_enforces_evidence_scope_and_three_iteration_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "surface.css"
            source.write_text(".panel { width: 760px; }\n", encoding="utf-8")
            plan = {
                "id": "RP-TEST", "taskId": "TEST", "authority": "visual-only", "iterationLimit": 3,
                "allowedFiles": ["surface.css"],
                "repairs": [{
                    "findingId": "overflow", "severity": "P1", "file": "surface.css",
                    "expected": "width: 760px", "replacement": "width: min(100%, 760px)", "evidenceId": "overflow",
                }],
            }
            evidence = {"findings": [{"id": "overflow"}]}
            dry_run = apply_repair_plan(root, plan, evidence, 1, apply=False)
            self.assertEqual(dry_run.status, "DRY_RUN")
            self.assertIn("760px", source.read_text(encoding="utf-8"))
            applied = apply_repair_plan(root, plan, evidence, 1, apply=True)
            self.assertEqual(applied.status, "APPLIED")
            self.assertIn("min(100%, 760px)", source.read_text(encoding="utf-8"))
            blocked = apply_repair_plan(root, plan, evidence, 4, apply=False)
            self.assertEqual(blocked.status, "BLOCKED")

    def test_repair_cannot_modify_baselines_or_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / ".design/baselines/surface/mobile/baseline.png"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"baseline")
            plan = {
                "id": "RP-BAD", "taskId": "TEST", "authority": "visual-only", "iterationLimit": 1,
                "allowedFiles": [".design/baselines/surface/mobile/baseline.png"],
                "repairs": [{
                    "findingId": "drift", "severity": "P1", "file": ".design/baselines/surface/mobile/baseline.png",
                    "expected": "baseline", "replacement": "changed", "evidenceId": "drift",
                }],
            }
            report = apply_repair_plan(root, plan, {"findings": [{"id": "drift"}]}, 1, apply=True)
            self.assertEqual(report.status, "BLOCKED")
            self.assertEqual(target.read_bytes(), b"baseline")

    def test_multiple_repairs_to_one_file_compose_in_plan_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "surface.css"
            source.write_text(".panel { width: 760px; color: #777; }\n", encoding="utf-8")
            plan = {
                "id": "RP-COMPOSE", "taskId": "TEST", "authority": "visual-only",
                "iterationLimit": 1, "allowedFiles": ["surface.css"],
                "repairs": [
                    {
                        "findingId": "overflow", "severity": "P1", "file": "surface.css",
                        "expected": "width: 760px", "replacement": "width: min(100%, 760px)",
                        "evidenceId": "overflow",
                    },
                    {
                        "findingId": "contrast", "severity": "P1", "file": "surface.css",
                        "expected": "color: #777", "replacement": "color: #333",
                        "evidenceId": "contrast",
                    },
                ],
            }
            evidence = {"findings": [{"id": "overflow"}, {"id": "contrast"}]}
            report = apply_repair_plan(root, plan, evidence, 1, apply=True)
            updated = source.read_text(encoding="utf-8")
            self.assertEqual(report.status, "APPLIED")
            self.assertEqual(report.changed_files, ["surface.css"])
            self.assertEqual(len(report.applied_repairs), 2)
            self.assertIn("width: min(100%, 760px)", updated)
            self.assertIn("color: #333", updated)

    def test_baseline_promotion_requires_accepted_decision_and_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("fixture", encoding="utf-8")
            initialize_memory(root)
            proposal = {
                "id": "DL-BASE-001", "status": "proposed", "authorityLevel": "product", "product": "test",
                "decision": "Govern baseline.", "problem": "Silent changes.", "evidence": ["directive"],
                "alternatives": ["silent"], "reason": "Traceability.", "affectedComponents": ["Surface"],
                "createdAt": "2026-08-20T12:00:00Z",
            }
            append_decision(root, proposal)
            append_outcome(root, {
                "id": "DO-BASE-001", "decisionId": "DL-BASE-001", "result": "accepted",
                "reason": "Checks passed.", "evidence": ["qa"], "lesson": "Govern changes.",
                "recordedAt": "2026-08-20T13:00:00Z",
            })
            append_decision(root, {**proposal, "status": "accepted", "revision": 2, "promotion": {
                "authorizedBy": "human:owner", "outcomeId": "DO-BASE-001", "validationEvidence": ["qa"],
            }})
            current = root / "current/mobile"
            current.mkdir(parents=True)
            (current / "current.png").write_bytes(b"png")
            approval = root / "approval.json"
            approval.write_text(json.dumps({
                "decisionId": "DL-BASE-001", "reason": "Initial governed image", "authorizedBy": "human:owner",
                "validationStatus": "PASS", "validationEvidence": ["qa"],
            }), encoding="utf-8")
            promote_baseline(root, "surface", root / "current", approval)
            self.assertEqual(audit_baselines(root)["status"], "PASS")

    def test_component_registry_is_repository_derived(self) -> None:
        registry = build_component_registry(FIXTURES / "mature-repo")
        self.assertTrue(any(item["path"] == "components/ui/Button.tsx" for item in registry["components"]))


if __name__ == "__main__":
    unittest.main()
