from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from io import StringIO

from design_intelligence.agentic import assess_outcome
from design_intelligence.cli import main as cli_main
from design_intelligence.memory import append_decision, initialize_memory
from design_intelligence.outcome_lifecycle import (
    audit_outcome_ratification_receipt,
    create_outcome_ratification_receipt,
    promote_outcome_from_receipt,
    retire_promoted_decision,
)


NOW = datetime(2026, 9, 13, 12, tzinfo=timezone.utc)


class OutcomeLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        initialize_memory(self.root, allow_existing_authority=True, memory_only=True)
        self.decision = {
            "id": "DL-OUTCOME-1",
            "status": "proposed",
            "authorityLevel": "surface",
            "surface": "Workspace",
            "decision": "Keep the validated interaction pattern.",
            "problem": "The outcome was previously unknown.",
            "evidence": ["assessment.json"],
            "alternatives": ["Retire the pattern."],
            "reason": "Awaiting outcome evidence.",
            "affectedComponents": ["Workspace"],
            "createdAt": "2026-09-01T00:00:00Z",
        }
        append_decision(self.root, self.decision)
        assessment = assess_outcome({
            "contract": {
                "id": "OUT-1",
                "decisionId": self.decision["id"],
                "journeyId": "JRN-1",
                "surface": "Workspace",
                "reason": "The task completion target was met without crossing the error bound.",
                "lesson": "Preserve the interaction while the measured result remains valid.",
                "observationWindow": {"start": "2026-09-01T00:00:00Z", "end": "2026-09-10T00:00:00Z"},
                "successSignals": [{"id": "completion", "actual": 0.8, "operator": ">=", "threshold": 0.75, "evidence": ["analytics:completion"]}],
                "counterSignals": [{"id": "errors", "actual": 0.01, "operator": "<=", "threshold": 0.02, "evidence": ["errors:rate"]}],
            },
            "releaseEvidence": ["release:sha"],
        }, as_of=NOW)
        self.assessment_path = self.root / "assessment.json"
        self.assessment_path.write_text(json.dumps(assessment), encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _receipt(self, *, authorized_by: str = "human:product-owner", action: str = "PROMOTE") -> Path:
        receipt_path = self.root / f"receipt-{action.lower()}.json"
        create_outcome_ratification_receipt(
            self.root,
            self.assessment_path,
            {
                "decision": action,
                "authorizedBy": authorized_by,
                "reason": "Reviewed the bound result and evidence.",
                "outcomeId": "DO-OUTCOME-1" if action == "PROMOTE" else None,
            },
            receipt_path,
            decided_at=NOW,
        )
        return receipt_path

    def test_agent_identity_cannot_ratify(self) -> None:
        with self.assertRaisesRegex(ValueError, "explicit human authority"):
            self._receipt(authorized_by="agent:codex")

    def test_receipt_is_hash_bound_and_expires(self) -> None:
        receipt_path = self._receipt()
        self.assessment_path.write_text("{}", encoding="utf-8")
        tampered = audit_outcome_ratification_receipt(self.root, receipt_path, as_of=NOW)
        self.assertEqual(tampered["status"], "FAIL")
        self.assertIn("receipt.assessmentEvidence hash mismatch", tampered["errors"])

        receipt_path.unlink()
        assessment = assess_outcome({
            "contract": {
                "id": "OUT-1", "decisionId": "DL-OUTCOME-1", "journeyId": "JRN-1",
                "observationWindow": {"start": "2026-09-01T00:00:00Z", "end": "2026-09-10T00:00:00Z"},
                "successSignals": [{"id": "ok", "actual": 1, "operator": ">=", "threshold": 1, "evidence": ["signal"]}],
                "counterSignals": [],
            },
            "releaseEvidence": ["release"],
        }, as_of=NOW)
        self.assessment_path.write_text(json.dumps(assessment), encoding="utf-8")
        receipt_path = self._receipt()
        expired = audit_outcome_ratification_receipt(self.root, receipt_path, as_of=NOW + timedelta(days=8))
        self.assertIn("receipt has expired", expired["errors"])

    def test_promotion_appends_canonical_outcome_once(self) -> None:
        receipt_path = self._receipt()
        report = promote_outcome_from_receipt(self.root, receipt_path, as_of=NOW)
        self.assertEqual(report["status"], "PROMOTED")
        outcomes = (self.root / ".design/memory/outcomes.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(outcomes), 1)
        with self.assertRaisesRegex(ValueError, "Duplicate outcome id"):
            promote_outcome_from_receipt(self.root, receipt_path, as_of=NOW)

    def test_rejected_receipt_cannot_promote(self) -> None:
        receipt_path = self._receipt(action="REJECT")
        with self.assertRaisesRegex(ValueError, "not PROMOTE"):
            promote_outcome_from_receipt(self.root, receipt_path, as_of=NOW)

    def test_cli_audits_exact_receipt(self) -> None:
        receipt_path = self._receipt()
        with redirect_stdout(StringIO()) as output:
            code = cli_main([
                "agentic", "outcome-ratification-audit", "--root", str(self.root),
                "--input", str(receipt_path), "--as-of", "2026-09-13T12:00:00Z", "--format", "json",
            ])
        report = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "PASS")

    def test_retirement_requires_human_and_preserves_revision_history(self) -> None:
        receipt_path = self._receipt()
        promote_outcome_from_receipt(self.root, receipt_path, as_of=NOW)
        accepted = {**self.decision, "status": "accepted", "revision": 2, "createdAt": "2026-09-13T12:00:00Z", "promotion": {
            "authorizedBy": "human:product-owner",
            "outcomeId": "DO-OUTCOME-1",
            "validationEvidence": ["assessment.json", "receipt-promote.json"],
        }}
        append_decision(self.root, accepted)
        with self.assertRaisesRegex(ValueError, "explicit human authority"):
            retire_promoted_decision(self.root, {"decisionId": "DL-OUTCOME-1", "authorizedBy": "agent:codex", "reason": "Changed."}, retired_at=NOW)
        report = retire_promoted_decision(self.root, {"decisionId": "DL-OUTCOME-1", "authorizedBy": "human:product-owner", "reason": "A later observed result invalidated the pattern."}, retired_at=NOW)
        self.assertEqual(report["status"], "RETIRED")
        self.assertEqual(report["decision"]["revision"], 3)
        self.assertEqual(report["decision"]["status"], "deprecated")
        self.assertEqual(len((self.root / ".design/memory/decisions.jsonl").read_text(encoding="utf-8").splitlines()), 3)


if __name__ == "__main__":
    unittest.main()
