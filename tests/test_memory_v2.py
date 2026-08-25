from __future__ import annotations

import tempfile
import unittest
import hashlib
import json
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
    preflight_memory,
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


def accept_surface_decision(root: Path, decision_id: str) -> dict:
    proposal = proposed_decision(decision_id)
    append_decision(root, proposal)
    outcome_id = decision_id.replace("DL-", "DO-", 1)
    append_outcome(root, {
        "id": outcome_id,
        "decisionId": decision_id,
        "result": "accepted",
        "reason": "Rendered checks passed.",
        "evidence": ["qa:pass"],
        "lesson": "The scoped rule held.",
        "product": "quotepilot",
        "surface": "Quote Workspace",
        "recordedAt": "2026-08-20T13:00:00Z",
    })
    accepted = {
        **proposal,
        "status": "accepted",
        "revision": 2,
        "promotion": {
            "authorizedBy": "quality-gate",
            "outcomeId": outcome_id,
            "validationEvidence": ["qa:pass"],
        },
    }
    append_decision(root, accepted)
    return accepted


class MemoryV2Tests(unittest.TestCase):
    def test_preflight_blocks_when_memory_is_not_initialized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("fixture", encoding="utf-8")

            preflight = preflight_memory(root, product="quietpilot")

            self.assertEqual(preflight["status"], "BLOCK")
            self.assertEqual(len(preflight["blockers"]), 4)
            self.assertIn("decisions.jsonl", " ".join(preflight["blockers"]))

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
            self.assertEqual(context.decisions[0]["memoryClass"], "binding")
            self.assertEqual([item["id"] for item in context.binding_decisions], ["DL-TEST-001"])
            self.assertEqual(context.advisory_decisions, [])
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

    def test_memory_only_integration_does_not_install_quality_or_baselines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("fixture", encoding="utf-8")

            report = initialize_memory(root, memory_only=True)

            self.assertTrue(report["memoryOnly"])
            self.assertTrue((root / ".design/memory/product-rules.json").is_file())
            self.assertFalse((root / ".design/quality").exists())
            self.assertFalse((root / ".design/baselines").exists())

    def test_index_only_rules_fail_closed_when_source_authority_drifts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            authority = root / "docs/DESIGN_SYSTEM.md"
            authority.parent.mkdir(parents=True)
            authority.write_text("# Canonical design system\n", encoding="utf-8")
            initialize_memory(root, allow_existing_authority=True, memory_only=True)
            rules = {
                "schemaVersion": 1,
                "authorityMode": "index-only",
                "sourceAuthorities": [{
                    "path": "docs/DESIGN_SYSTEM.md",
                    "sha256": hashlib.sha256(authority.read_bytes()).hexdigest(),
                    "role": "visual-execution",
                }],
                "portfolio": [],
                "archetypes": {},
                "products": {
                    "quotepilot": {
                        "archetype": "transactional-commercial",
                        "rules": [{
                            "id": "DL-QP-INDEX-001",
                            "category": "evidence",
                            "statement": "Canonical repository design authority outranks memory summaries.",
                            "protected": True,
                            "sourceAuthority": "docs/DESIGN_SYSTEM.md",
                        }],
                    }
                },
            }
            (root / ".design/memory/product-rules.json").write_text(
                json.dumps(rules), encoding="utf-8"
            )

            self.assertEqual(audit_memory(root)["status"], "PASS")
            authority.write_text("# Changed design system\n", encoding="utf-8")
            audit = audit_memory(root)

            self.assertEqual(audit["status"], "FAIL")
            self.assertIn("Source authority hash mismatch", " ".join(audit["errors"]))

    def test_experimental_decision_cannot_claim_supersession(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("fixture", encoding="utf-8")
            initialize_memory(root)
            accept_surface_decision(root, "DL-TEST-BASE")
            experimental = {
                **proposed_decision("DL-TEST-CANDIDATE"),
                "status": "experimental",
                "supersedes": "DL-TEST-BASE",
            }

            with self.assertRaisesRegex(ValueError, "cannot declare supersedes"):
                append_decision(root, experimental)

    def test_corrected_latest_revision_rehabilitates_historical_lifecycle_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("fixture", encoding="utf-8")
            initialize_memory(root)
            accept_surface_decision(root, "DL-TEST-BASE")
            invalid = {
                **proposed_decision("DL-TEST-CANDIDATE"),
                "status": "experimental",
                "revision": 1,
                "supersedes": "DL-TEST-BASE",
            }
            decisions_path = root / ".design/memory/decisions.jsonl"
            with decisions_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(invalid) + "\n")

            self.assertEqual(audit_memory(root)["status"], "FAIL")

            corrected = {
                **invalid,
                "revision": 2,
                "supersedes": None,
                "proposesSupersession": "DL-TEST-BASE",
            }
            append_decision(root, corrected)
            preflight = preflight_memory(
                root,
                product="quotepilot",
                surface="Quote Workspace",
                as_of=date(2026, 8, 20),
            )

            self.assertEqual(preflight["status"], "WARN")
            self.assertEqual(preflight["audit"]["status"], "PASS")
            self.assertEqual(preflight["advisoryDecisions"][0]["revision"], 2)

    def test_rejected_outcome_blocks_accepted_law_until_lifecycle_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("fixture", encoding="utf-8")
            initialize_memory(root)
            accepted = accept_surface_decision(root, "DL-TEST-LIFECYCLE")
            append_outcome(root, {
                "id": "DO-TEST-LIFECYCLE-REJECTED",
                "decisionId": "DL-TEST-LIFECYCLE",
                "result": "rejected",
                "reason": "The later rendered outcome failed.",
                "evidence": ["qa:regression"],
                "lesson": "The law must be retired or replaced.",
                "product": "quotepilot",
                "surface": "Quote Workspace",
                "recordedAt": "2026-08-21T13:00:00Z",
            })

            blocked = preflight_memory(
                root,
                product="quotepilot",
                surface="Quote Workspace",
                as_of=date(2026, 8, 21),
            )
            self.assertEqual(blocked["status"], "BLOCK")
            self.assertIn("later rejected outcome", " ".join(blocked["blockers"]))

            append_decision(root, {
                **accepted,
                "revision": 3,
                "status": "deprecated",
                "lifecycleReason": "A later rejected outcome invalidated the binding law.",
            })
            warning = preflight_memory(
                root,
                product="quotepilot",
                surface="Quote Workspace",
                as_of=date(2026, 8, 21),
            )

            self.assertEqual(warning["status"], "WARN")
            self.assertEqual(warning["bindingDecisions"], [])
            self.assertEqual(warning["historicalDecisions"][0]["status"], "deprecated")

    def test_accepted_supersession_requires_bidirectional_lifecycle_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("fixture", encoding="utf-8")
            initialize_memory(root)
            original = accept_surface_decision(root, "DL-TEST-ORIGINAL")
            candidate = {
                **proposed_decision("DL-TEST-SUCCESSOR"),
                "proposesSupersession": "DL-TEST-ORIGINAL",
            }
            append_decision(root, candidate)
            append_outcome(root, {
                "id": "DO-TEST-SUCCESSOR",
                "decisionId": "DL-TEST-SUCCESSOR",
                "result": "accepted",
                "reason": "The replacement passed rendered checks.",
                "evidence": ["qa:replacement-pass"],
                "lesson": "Replace the original law explicitly.",
                "recordedAt": "2026-08-21T13:00:00Z",
            })
            successor = {
                **candidate,
                "revision": 2,
                "status": "accepted",
                "supersedes": "DL-TEST-ORIGINAL",
                "promotion": {
                    "authorizedBy": "quality-gate",
                    "outcomeId": "DO-TEST-SUCCESSOR",
                    "validationEvidence": ["qa:replacement-pass"],
                },
            }
            successor.pop("proposesSupersession")
            append_decision(root, successor)

            self.assertEqual(audit_memory(root)["status"], "FAIL")

            append_decision(root, {
                **original,
                "revision": 3,
                "status": "superseded",
                "supersededBy": "DL-TEST-SUCCESSOR",
            })
            audit = audit_memory(root)
            context = retrieve_context(root, product="quotepilot", surface="Quote Workspace")

            self.assertEqual(audit["status"], "PASS")
            self.assertEqual([item["id"] for item in context.binding_decisions], ["DL-TEST-SUCCESSOR"])
            self.assertEqual([item["id"] for item in context.historical_decisions], ["DL-TEST-ORIGINAL"])

    def test_audit_detects_manual_supersession_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("fixture", encoding="utf-8")
            initialize_memory(root)
            records = []
            for decision_id, target in (("DL-TEST-A", "DL-TEST-B"), ("DL-TEST-B", "DL-TEST-A")):
                records.append({
                    **proposed_decision(decision_id),
                    "revision": 1,
                    "status": "deprecated",
                    "supersedes": target,
                })
            (root / ".design/memory/decisions.jsonl").write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )

            audit = audit_memory(root)

            self.assertEqual(audit["status"], "FAIL")
            self.assertIn("Supersession cycle detected", " ".join(audit["errors"]))


if __name__ == "__main__":
    unittest.main()
