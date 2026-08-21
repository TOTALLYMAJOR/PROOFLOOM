from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from design_intelligence.memory import (
    append_debt,
    append_decision,
    append_exception,
    append_outcome,
    audit_memory,
    find_stale_records,
    initialize_memory,
    retrieve_context,
)


FIXTURES = Path(__file__).parent / "fixtures"


def proposed_decision(decision_id: str = "DL-TEST-001") -> dict:
    return {
        "id": decision_id,
        "status": "proposed",
        "authorityLevel": "surface",
        "product": "quotepilot",
        "surface": "Quote Workspace",
        "decision": "Keep quote construction primary.",
        "problem": "Secondary controls competed with quote creation.",
        "evidence": ["test:evidence"],
        "alternatives": ["equal columns"],
        "reason": "The primary task must remain visible.",
        "affectedComponents": ["QuoteWorkspace"],
        "createdAt": "2026-08-20T12:00:00Z",
        "reviewAfter": "2026-08-01",
    }


class MemoryV2Tests(unittest.TestCase):
    def test_promotion_requires_outcome_and_supports_bounded_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("fixture", encoding="utf-8")
            initialize_memory(root)
            append_decision(root, proposed_decision())
            append_outcome(
                root,
                {
                    "id": "DO-TEST-001",
                    "decisionId": "DL-TEST-001",
                    "result": "accepted",
                    "reason": "Rendered checks passed.",
                    "evidence": ["qa:pass"],
                    "lesson": "Primary task hierarchy held at mobile.",
                    "product": "quotepilot",
                    "surface": "Quote Workspace",
                    "recordedAt": "2026-08-20T13:00:00Z",
                },
            )
            accepted = {**proposed_decision(), "status": "accepted", "revision": 2, "promotion": {
                "authorizedBy": "quality-gate",
                "outcomeId": "DO-TEST-001",
                "validationEvidence": ["qa:pass"],
            }}
            append_decision(root, accepted)
            append_debt(
                root,
                {
                    "id": "DD-TEST-001",
                    "status": "open",
                    "description": "Review mobile secondary controls.",
                    "scope": {"product": "quotepilot", "surface": "Quote Workspace"},
                    "owner": "design-owner",
                    "createdAt": "2026-07-01T00:00:00Z",
                    "reviewAfter": "2026-08-01",
                },
            )
            context = retrieve_context(root, product="quotepilot", surface="Quote Workspace", max_records=2, as_of=date(2026, 8, 20))

            self.assertEqual(context.decisions[0]["status"], "accepted")
            self.assertTrue(context.bounded)
            self.assertTrue(any(item["id"] == "DL-PORT-001" for item in context.inherited_rules))
            self.assertGreaterEqual(len(find_stale_records(root, date(2026, 8, 20))), 2)
            self.assertEqual(audit_memory(root, date(2026, 8, 20))["status"], "PASS")

    def test_agent_cannot_promote_product_law(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("fixture", encoding="utf-8")
            initialize_memory(root)
            proposal = {**proposed_decision(), "authorityLevel": "product", "surface": None}
            append_decision(root, proposal)
            append_outcome(root, {
                "id": "DO-TEST-001", "decisionId": "DL-TEST-001", "result": "accepted",
                "reason": "One run passed.", "evidence": ["qa:pass"], "lesson": "Local evidence only.",
                "recordedAt": "2026-08-20T13:00:00Z",
            })
            accepted = {**proposal, "status": "accepted", "revision": 2, "promotion": {
                "authorizedBy": "agent:auto", "outcomeId": "DO-TEST-001", "validationEvidence": ["qa:pass"],
            }}
            with self.assertRaisesRegex(ValueError, "explicit human authority"):
                append_decision(root, accepted)

    def test_exception_cannot_weaken_accessibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("fixture", encoding="utf-8")
            initialize_memory(root)
            with self.assertRaisesRegex(ValueError, "cannot weaken accessibility"):
                append_exception(root, {
                    "id": "DX-TEST-001",
                    "reason": "Temporary visual shortcut.",
                    "scope": {"product": "quotepilot"},
                    "owner": "design-owner",
                    "createdAt": "2026-08-20T12:00:00Z",
                    "expiresAt": "2026-09-20",
                    "status": "active",
                    "categories": ["accessibility"],
                })

    def test_existing_memory_authority_blocks_duplicate_fallback(self) -> None:
        with self.assertRaisesRegex(ValueError, "Existing design-decision authority"):
            initialize_memory(FIXTURES / "mature-repo")


if __name__ == "__main__":
    unittest.main()
