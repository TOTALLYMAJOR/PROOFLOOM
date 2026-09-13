from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

from design_intelligence.agentic import (
    analyze_ux_state_graph,
    assess_outcome,
    build_authority_capsule,
    evaluate_design_arena,
    simulate_counterfactual,
)
from design_intelligence.cli import main as cli_main


class AgenticCapabilityTests(unittest.TestCase):
    def test_agentic_output_schemas_are_packaged_json_contracts(self) -> None:
        schema_root = Path(__file__).parents[1] / "design_intelligence/data/schemas"
        names = {
            "authority-capsule.schema.json": "design-intelligence/authority-capsule",
            "ux-state-graph.schema.json": "design-intelligence/ux-state-graph",
            "counterfactual-report.schema.json": "design-intelligence/counterfactual-report",
            "design-arena-report.schema.json": "design-intelligence/design-arena-report",
            "outcome-assessment.schema.json": "design-intelligence/outcome-assessment",
            "outcome-ratification-receipt.schema.json": "design-intelligence/outcome-ratification-receipt",
        }
        for name, kind in names.items():
            schema = json.loads((schema_root / name).read_text(encoding="utf-8"))
            self.assertEqual(schema["properties"]["kind"]["const"], kind)

    def test_authority_capsule_verifies_sources_and_orders_claims(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "AGENTS.md"
            source.write_text("governed\n", encoding="utf-8")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            report = build_authority_capsule(
                root,
                {
                    "taskId": "TASK-1",
                    "phase": "implement",
                    "asOf": "2026-09-13T12:00:00Z",
                    "maxClaims": 1,
                    "claims": [
                        {
                            "id": "lower-authority",
                            "statement": "A convention applies.",
                            "classification": "INFERRED",
                            "authorityRank": 5,
                            "priority": 10,
                        },
                        {
                            "id": "repository-rule",
                            "statement": "Repository governance applies.",
                            "classification": "ESTABLISHED",
                            "authorityRank": 2,
                            "priority": 1,
                            "source": {"path": "AGENTS.md", "sha256": digest},
                        },
                    ],
                },
            )
        self.assertEqual(report["status"], "READY")
        self.assertEqual(report["claims"][0]["id"], "repository-rule")
        self.assertEqual(report["omittedClaimIds"], ["lower-authority"])
        self.assertFalse(report["implementationAuthorized"])

    def test_authority_capsule_fails_closed_on_source_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "authority.md").write_text("changed\n", encoding="utf-8")
            report = build_authority_capsule(
                root,
                {
                    "taskId": "TASK-2",
                    "phase": "plan",
                    "claims": [{
                        "id": "authority",
                        "statement": "The source is current.",
                        "classification": "ESTABLISHED",
                        "authorityRank": 1,
                        "source": {"path": "authority.md", "sha256": "a" * 64},
                    }],
                },
                as_of=datetime(2026, 9, 13, tzinfo=timezone.utc),
            )
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["invalidSources"][0]["reason"], "DRIFTED")

    def test_state_graph_finds_negative_path_and_recovery_gaps(self) -> None:
        report = analyze_ux_state_graph({
            "journeyId": "JRN-CHECKOUT",
            "requiredStateKinds": ["start", "loading", "error", "success"],
            "states": [
                {"id": "ready", "kind": "start"},
                {"id": "failed", "kind": "error"},
                {"id": "done", "kind": "success"},
            ],
            "transitions": [
                {"from": "ready", "to": "failed", "event": "submit"},
                {"from": "ready", "to": "done", "event": "complete"},
            ],
        })
        self.assertEqual(report["status"], "REVIEW_REQUIRED")
        self.assertEqual(report["coverage"]["missingStateKinds"], ["loading"])
        self.assertEqual(report["coverage"]["unrecoverableStateIds"], ["failed"])
        self.assertGreaterEqual(len(report["proposedScenarios"]), 2)

    def test_counterfactual_blocks_boundary_crossing_and_recommends_evidence(self) -> None:
        report = simulate_counterfactual({
            "proposalId": "PROP-1",
            "protectedBoundaries": ["pricing"],
            "alternatives": [
                {
                    "id": "safe",
                    "summary": "Clarify hierarchy without changing price authority.",
                    "effects": [{
                        "dimension": "journey",
                        "target": "comparison",
                        "direction": "improve",
                        "confidence": "HIGH",
                        "evidence": ["baseline-a"],
                        "falsificationTest": "Task completion does not improve.",
                    }],
                    "requiredEvidence": ["five viewports"],
                    "rollbackSignals": ["serious accessibility regression"],
                    "boundaryImpacts": [],
                },
                {
                    "id": "unsafe",
                    "summary": "Change displayed pricing.",
                    "effects": [{
                        "dimension": "commercial",
                        "target": "pricing",
                        "direction": "change",
                        "confidence": "LOW",
                        "evidence": [],
                        "falsificationTest": "Price differs from authority.",
                    }],
                    "requiredEvidence": [],
                    "rollbackSignals": ["price mismatch"],
                    "boundaryImpacts": [{"boundary": "pricing", "status": "PROPOSED"}],
                },
            ],
        })
        self.assertEqual(report["recommendedAlternativeId"], "safe")
        self.assertFalse(report["implementationAuthorized"])
        unsafe = next(item for item in report["alternatives"] if item["id"] == "unsafe")
        self.assertFalse(unsafe["eligibleForSelection"])

    def test_design_arena_requires_comparable_isolated_receipts(self) -> None:
        contract_hash = "b" * 64
        validation_plan_hash = "c" * 64
        evidence = {
            "dimensions": ["visual", "accessibility"],
            "qualityScore": 92,
            "criticalAccessibilityViolations": 0,
            "seriousAccessibilityViolations": 0,
            "testsPassed": 5,
            "testsTotal": 5,
            "proofComplete": True,
        }
        report = evaluate_design_arena({
            "arenaId": "ARENA-1",
            "contractHash": contract_hash,
            "validationPlanHash": validation_plan_hash,
            "requiredEvidenceDimensions": ["visual", "accessibility"],
            "minimumIndependentReviews": 2,
            "variants": [
                {
                    "id": "a",
                    "contractHash": contract_hash,
                    "validationPlanHash": validation_plan_hash,
                    "workspaceIsolation": True,
                    "buildReceiptStatus": "PASS",
                    "evidence": evidence,
                    "reviews": [
                        {"reviewerId": "critic-1", "verdict": "PASS", "findings": []},
                        {"reviewerId": "critic-2", "verdict": "PASS", "findings": []},
                    ],
                },
                {
                    "id": "b",
                    "contractHash": contract_hash,
                    "validationPlanHash": validation_plan_hash,
                    "workspaceIsolation": False,
                    "buildReceiptStatus": "PASS",
                    "evidence": {**evidence, "qualityScore": 99},
                    "reviews": [
                        {"reviewerId": "critic-1", "verdict": "PASS", "findings": []},
                        {"reviewerId": "critic-2", "verdict": "BLOCKED", "findings": ["Hierarchy regression"]},
                    ],
                },
            ],
        })
        self.assertEqual(report["leaderVariantId"], "a")
        self.assertTrue(report["humanSelectionRequired"])
        self.assertFalse(report["executionPerformed"])
        blocked = next(item for item in report["variants"] if item["variantId"] == "b")
        self.assertTrue(blocked["dissent"])

    def test_outcome_assessment_separates_success_from_ratification(self) -> None:
        report = assess_outcome(
            {
                "contract": {
                    "id": "OUT-1",
                    "decisionId": "DL-OUTCOME-1",
                    "journeyId": "JRN-1",
                    "observationWindow": {"start": "2026-09-01T00:00:00Z", "end": "2026-09-10T00:00:00Z"},
                    "successSignals": [{"id": "completion", "actual": 0.8, "operator": ">=", "threshold": 0.75, "evidence": ["analytics:completion"]}],
                    "counterSignals": [{"id": "errors", "actual": 0.01, "operator": "<=", "threshold": 0.02, "evidence": ["errors:rate"]}],
                },
                "releaseEvidence": ["release:sha"],
                "agentSignals": [{"id": "escaped-defects", "actual": 0, "operator": "<=", "threshold": 0, "evidence": ["qa:defects"]}],
            },
            as_of=datetime(2026, 9, 13, tzinfo=timezone.utc),
        )
        self.assertEqual(report["outcomeStatus"], "SUCCESS")
        self.assertTrue(report["memoryCandidate"]["eligible"])
        self.assertEqual(report["memoryCandidate"]["ratificationStatus"], "HUMAN_REQUIRED")
        self.assertFalse(report["memoryMutationPerformed"])

    def test_outcome_assessment_blocks_incomplete_observation(self) -> None:
        report = assess_outcome(
            {
                "contract": {
                    "id": "OUT-2",
                    "decisionId": "DL-OUTCOME-2",
                    "journeyId": "JRN-2",
                    "observationWindow": {"start": "2026-09-01T00:00:00Z", "end": "2026-09-20T00:00:00Z"},
                    "successSignals": [{"id": "completion", "actual": 1, "operator": ">=", "threshold": 1, "evidence": ["analytics"]}],
                    "counterSignals": [],
                },
                "releaseEvidence": ["release"],
            },
            as_of=datetime(2026, 9, 13, tzinfo=timezone.utc),
        )
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["outcomeStatus"], "NOT_READY")

    def test_cli_writes_only_to_explicit_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "state-input.json"
            output = root / "state-report.json"
            source.write_text(json.dumps({
                "journeyId": "JRN-CLI",
                "requiredStateKinds": ["start", "success"],
                "states": [{"id": "start", "kind": "start"}, {"id": "done", "kind": "success"}],
                "transitions": [{"from": "start", "to": "done", "event": "finish"}],
            }), encoding="utf-8")
            with redirect_stdout(StringIO()):
                code = cli_main(["agentic", "state-graph", "--input", str(source), "--output", str(output), "--format", "json"])
            written = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        self.assertEqual(written["status"], "PASS")
        self.assertEqual(written["kind"], "design-intelligence/ux-state-graph")


if __name__ == "__main__":
    unittest.main()
