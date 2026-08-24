from __future__ import annotations

import hashlib
import json
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from design_intelligence.adoption import (
    audit_adoption_report,
    audit_design_system_health,
    discover_adoption_authorities,
    evaluate_adoption,
    save_adoption_bundle,
)
from design_intelligence.contracts import validate_contract
from design_intelligence.memory import initialize_memory
from design_intelligence.workflows import build_start_packet


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class AdoptionGateTests(unittest.TestCase):
    def test_unresearched_reference_cannot_authorize_implementation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Product\n", encoding="utf-8")

            report = evaluate_adoption(
                root,
                "Improve the proposal workspace",
                references=["https://example.com/reference"],
            )

            self.assertEqual(report["status"], "RESEARCH_REQUIRED")
            self.assertFalse(report["implementationReady"])
            self.assertEqual(report["sources"][0]["status"], "RESEARCH_REQUIRED")
            self.assertFalse(report["implementationPerformed"])
            self.assertFalse(report["baselineMutationPerformed"])

    def test_deferred_governance_receipt_blocks_report_and_mission_implementation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_healthy_repository(root)
            image = root / "reference.png"
            image.write_bytes(
                b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 900, 600)
            )
            task = "Improve image-backed hierarchy under a governed hold"
            analysis = self._analysis_for({
                "id": "PAT-HOLD-FOCUS",
                "source": "reference.png",
                "name": "Focused hierarchy",
                "category": "layout",
                "observation": "One decision precedes supporting detail.",
                "whyItWorks": "It lowers decision search cost.",
                "productRelevance": "The workflow has one primary decision.",
                "proposedUse": "Place the decision before supporting detail.",
                "keywords": ["focused hierarchy"],
                "requiredCapabilities": [],
                "riskFlags": [],
                "identityElements": [],
                "implementationImpact": "visual-only",
            })
            receipt = (
                REPOSITORY_ROOT
                / "artifacts/design/baseline-decisions/quotepilot-hold-2026-08-21.json"
            )

            report = evaluate_adoption(
                root,
                task,
                images=["reference.png"],
                analysis=analysis,
                governance_receipts=[receipt],
            )

            self.assertEqual(report["status"], "REVIEW_REQUIRED")
            self.assertFalse(report["implementationReady"])
            self.assertEqual(report["governanceConstraints"]["status"], "HELD")
            self.assertEqual(
                report["governanceConstraints"]["receipts"][0]["receiptId"],
                "BDR-B597544BA89A63A0",
            )
            outputs = save_adoption_bundle(
                report,
                root / "artifacts/design/adoptions/held-hierarchy",
            )

            packet = build_start_packet(
                str(root),
                task,
                references=[],
                images=["reference.png"],
                direction="recommended",
                adoption_report=outputs["report"],
            )

            self.assertEqual(packet["status"], "ADOPTION_BLOCKED")
            self.assertFalse(packet["mission"]["implementationReady"])

    def test_product_profile_adoption_requires_configured_institutional_memory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_healthy_repository(root)
            image = root / "reference.png"
            image.write_bytes(
                b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 900, 600)
            )
            analysis = self._analysis_for({
                "id": "PAT-MEMORY-FOCUS",
                "source": "reference.png",
                "name": "Commercial decision hierarchy",
                "category": "layout",
                "observation": "The next commercial decision is visually primary.",
                "whyItWorks": "It improves confidence and speed.",
                "productRelevance": "QuotePilot is a transactional commercial product.",
                "proposedUse": "Prioritize the commercial next action.",
                "keywords": ["commercial decision"],
                "requiredCapabilities": [],
                "riskFlags": [],
                "identityElements": [],
                "implementationImpact": "visual-only",
            })

            report = evaluate_adoption(
                root,
                "Improve quote decision hierarchy",
                images=["reference.png"],
                analysis=analysis,
                profile_name="quotepilot",
                surface="Proposal review",
            )

            self.assertTrue(report["memoryRequired"])
            self.assertEqual(report["memoryContext"]["status"], "NOT_CONFIGURED")
            self.assertEqual(report["governanceConstraints"]["status"], "REQUIRED")
            self.assertEqual(report["status"], "REVIEW_REQUIRED")
            self.assertFalse(report["implementationReady"])
            self.assertIsNone(report["designContract"])

    def test_authority_discovery_distinguishes_backlog_hooks_and_custom_instructions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {
                "AGENTS.md": "# Rules\nDo not imply unverified product state.\n",
                "BACKLOG.md": "# Accepted\n- [status: accepted] Preserve quote approval authority.\n",
                "docs/design-system.md": "# Design system\nUse the existing action hierarchy.\n",
                ".github/copilot-instructions.md": "Keep tenant state explicit.\n",
                ".husky/pre-commit": "npm run design:ci:quick\n",
            }
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            authorities = discover_adoption_authorities(root)

            kinds = {item["kind"] for item in authorities["sources"]}
            self.assertEqual(
                kinds,
                {"agent-governance", "backlog", "design-authority", "custom-instructions", "hook"},
            )
            self.assertTrue(all(item["sha256"] for item in authorities["sources"]))
            backlog = next(item for item in authorities["sources"] if item["kind"] == "backlog")
            self.assertEqual(backlog["statements"][0]["status"], "accepted")

    def test_underscore_design_authorities_are_discovered_without_false_competition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {
                "package.json": '{"dependencies":{"react":"1.0.0"},"devDependencies":{"axe-core":"1.0.0"}}',
                "components/ui/Button.tsx": "export const Button = () => null;",
                "docs/DESIGN_SYSTEM.md": "# Design System\nOwns visual execution details.\n",
                "docs/DESIGN_PRINCIPLES.md": "# Design Principles\nOwns product judgment.\n",
                "docs/DESIGN-CONTRACT.md": "# Design Contract\nOwns workflow composition.\n",
                "styles/globals.css": ":root { --space-2: 8px; } .x { gap: var(--space-2); }",
            }
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            authorities = discover_adoption_authorities(root)
            health = audit_design_system_health(root)

            authority_paths = {item["path"] for item in authorities["sources"]}
            self.assertTrue({
                "docs/DESIGN_SYSTEM.md",
                "docs/DESIGN_PRINCIPLES.md",
                "docs/DESIGN-CONTRACT.md",
            }.issubset(authority_paths))
            self.assertEqual(health["status"], "HEALTHY")
            self.assertEqual(health["evidence"]["designDocumentation"]["status"], "PRESENT")
            self.assertNotIn("design_language", health["conflicts"])

    def test_design_system_presence_is_not_treated_as_health(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {
                "package.json": '{"dependencies":{"react":"1.0.0"}}',
                "components/Button.tsx": "export const Button = () => null;",
                "components2/Button.tsx": "export const Button = () => null;",
                "docs/design-system.md": "# Design System\nUse blue buttons.\n",
                "design/DESIGN-LANGUAGE.md": "# Design Language\nUse red buttons.\n",
                "styles/globals.css": ":root { --color-primary: blue; }",
            }
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            health = audit_design_system_health(root)

            self.assertEqual(health["status"], "CONFLICTED")
            self.assertFalse(health["safeToExtend"])
            self.assertIn("design_language", health["conflicts"])
            self.assertIn("component_system", health["conflicts"])
            self.assertIn("converge", " ".join(health["requiredActions"]).lower())

    def test_feature_is_declined_when_required_product_capability_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Product\n", encoding="utf-8")
            image = root / "reference.png"
            image.write_bytes(
                b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 1440, 900)
            )
            absence_evidence = self._write_capability_search_evidence(root, "realtime-presence")
            analysis = {
                "schemaVersion": 1,
                "analyzer": {
                    "type": "model",
                    "name": "test-vision-adapter",
                    "observedAt": "2026-08-23T12:00:00Z",
                },
                "capabilityClaims": [
                    {
                        "capability": "realtime-presence",
                        "status": "ABSENT",
                        "evidenceMethod": "repository-search",
                        "evidence": [absence_evidence],
                    }
                ],
                "patterns": [
                    {
                        "id": "PAT-PRESENCE",
                        "source": "reference.png",
                        "name": "Live collaborator presence",
                        "category": "feature",
                        "observation": "Avatars indicate who is currently online.",
                        "whyItWorks": "It helps teams coordinate.",
                        "productRelevance": "Would show whether a quote editor is active.",
                        "proposedUse": "Add live presence dots beside quote editors.",
                        "keywords": ["presence", "online"],
                        "requiredCapabilities": ["realtime-presence"],
                        "riskFlags": ["false-authoritative-state"],
                        "identityElements": [],
                        "implementationImpact": "backend",
                    }
                ],
            }

            report = evaluate_adoption(
                root,
                "Evaluate collaborator presence",
                images=["reference.png"],
                analysis=analysis,
            )

            self.assertEqual(report["status"], "DECLINED")
            self.assertEqual(report["decisions"][0]["decision"], "DECLINE")
            self.assertIn("realtime-presence", " ".join(report["decisions"][0]["reasons"]))
            self.assertFalse(report["implementationReady"])
            self.assertEqual(report["sources"][0]["dimensions"], {"width": 1440, "height": 900})

    def test_bare_absent_capability_claim_is_downgraded_to_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_healthy_repository(root)
            image = root / "reference.png"
            image.write_bytes(
                b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 900, 600)
            )
            analysis = self._analysis_for({
                "id": "PAT-UNPROVEN-ABSENCE",
                "source": "reference.png",
                "name": "Automatic approval",
                "category": "workflow",
                "observation": "The source automatically approves a quote.",
                "whyItWorks": "It removes a decision step.",
                "productRelevance": "QuotePilot has an explicit approval boundary.",
                "proposedUse": "Automatically approve a quote when opened.",
                "keywords": ["automatic approval"],
                "requiredCapabilities": ["automatic-approval-authority"],
                "riskFlags": [],
                "identityElements": [],
                "implementationImpact": "workflow",
            })
            analysis["capabilityClaims"] = [{
                "capability": "automatic-approval-authority",
                "status": "ABSENT",
                "evidence": [],
            }]

            report = evaluate_adoption(
                root,
                "Evaluate automatic approval",
                images=["reference.png"],
                analysis=analysis,
            )

            self.assertEqual(report["capabilityClaims"][0]["status"], "UNRESOLVED")
            self.assertEqual(report["decisions"][0]["decision"], "DEFER")
            self.assertEqual(report["status"], "REVIEW_REQUIRED")

    def test_accepted_backlog_constraint_blocks_conflicting_reference_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "BACKLOG.md").write_text(
                "# Accepted\n- [status: accepted] Do not add automatic quote acceptance.\n",
                encoding="utf-8",
            )
            image = root / "reference.png"
            image.write_bytes(
                b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 800, 600)
            )
            analysis = self._analysis_for({
                "id": "PAT-AUTO-ACCEPT",
                "source": "reference.png",
                "name": "Automatic quote acceptance",
                "category": "workflow",
                "observation": "A proposal becomes accepted when the customer opens it.",
                "whyItWorks": "It removes a confirmation step.",
                "productRelevance": "Could shorten the proposal flow.",
                "proposedUse": "Add automatic quote acceptance on open.",
                "keywords": ["automatic quote acceptance"],
                "requiredCapabilities": [],
                "riskFlags": [],
                "identityElements": [],
                "implementationImpact": "workflow",
            })

            report = evaluate_adoption(
                root,
                "Evaluate automatic acceptance",
                images=["reference.png"],
                analysis=analysis,
            )

            decision = report["decisions"][0]
            self.assertEqual(decision["decision"], "BLOCKED")
            self.assertIn("BACKLOG.md", " ".join(decision["reasons"]))
            self.assertFalse(report["implementationReady"])

    def test_healthy_repository_can_adopt_and_adapt_safe_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {
                "package.json": '{"dependencies":{"react":"1.0.0"},"devDependencies":{"@axe-core/playwright":"1.0.0"}}',
                "components/ui/Button.tsx": "export const Button = () => null;",
                "docs/design-system.md": "# Design System\nUse the existing action hierarchy.\n",
                "styles/globals.css": ":root { --color-primary: blue; } .button { color: var(--color-primary); }",
            }
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            image = root / "reference.png"
            image.write_bytes(
                b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 1200, 800)
            )
            analysis = self._analysis_for_patterns([
                {
                    "id": "PAT-HIERARCHY",
                    "source": "reference.png",
                    "name": "Decision-first hierarchy",
                    "category": "layout",
                    "observation": "The primary decision appears before supporting detail.",
                    "whyItWorks": "It lowers decision search cost.",
                    "productRelevance": "Proposal review has one dominant customer decision.",
                    "proposedUse": "Prioritize the proposal decision and consequence.",
                    "keywords": ["decision hierarchy"],
                    "requiredCapabilities": [],
                    "riskFlags": [],
                    "identityElements": [],
                    "implementationImpact": "visual-only",
                },
                {
                    "id": "PAT-BRANDED-CARD",
                    "source": "reference.png",
                    "name": "Branded summary card",
                    "category": "component",
                    "observation": "A branded card summarizes the selected option.",
                    "whyItWorks": "It keeps consequences close to selection.",
                    "productRelevance": "The quote summary needs stronger consequence visibility.",
                    "proposedUse": "Adapt the summary card using repository tokens and components.",
                    "keywords": ["summary card"],
                    "requiredCapabilities": [],
                    "riskFlags": [],
                    "identityElements": ["source palette", "source logo geometry"],
                    "implementationImpact": "component",
                },
            ])

            report = evaluate_adoption(
                root,
                "Improve proposal decision clarity",
                images=["reference.png"],
                analysis=analysis,
            )

            self.assertEqual(report["designSystemHealth"]["status"], "HEALTHY")
            self.assertEqual(report["status"], "READY")
            self.assertTrue(report["implementationReady"])
            self.assertEqual(
                [item["decision"] for item in report["decisions"]],
                ["ADOPT", "ADAPT"],
            )
            self.assertEqual(validate_contract(report["designContract"]), [])
            self.assertIn(
                "Prioritize the proposal decision and consequence.",
                report["designContract"]["change"],
            )
            self.assertIn("PAT-BRANDED-CARD", report["designContract"]["relevantDesignDecisions"])

    def test_url_analysis_without_bound_capture_remains_research_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Product\n", encoding="utf-8")
            analysis = self._analysis_for({
                "id": "PAT-NAV",
                "source": "https://example.com/reference",
                "name": "Compact navigation",
                "category": "navigation",
                "observation": "Navigation uses a compact rail.",
                "whyItWorks": "It preserves workspace width.",
                "productRelevance": "The product has dense workflows.",
                "proposedUse": "Evaluate a compact navigation rail.",
                "keywords": ["navigation rail"],
                "requiredCapabilities": [],
                "riskFlags": [],
                "identityElements": [],
                "implementationImpact": "visual-only",
            })

            report = evaluate_adoption(
                root,
                "Evaluate compact navigation",
                references=["https://example.com/reference"],
                analysis=analysis,
            )

            self.assertEqual(report["status"], "RESEARCH_REQUIRED")
            self.assertEqual(report["sources"][0]["status"], "RESEARCH_REQUIRED")
            self.assertEqual(report["decisions"], [])
            self.assertFalse(report["implementationReady"])

    def test_unproven_verified_capability_is_deferred(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Product\n", encoding="utf-8")
            image = root / "reference.png"
            image.write_bytes(
                b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 900, 600)
            )
            analysis = self._analysis_for({
                "id": "PAT-PRESENCE",
                "source": "reference.png",
                "name": "Presence indicator",
                "category": "feature",
                "observation": "A dot marks currently active users.",
                "whyItWorks": "It communicates collaboration context.",
                "productRelevance": "Editors may need coordination context.",
                "proposedUse": "Show active quote editors.",
                "keywords": ["presence indicator"],
                "requiredCapabilities": ["realtime-presence"],
                "riskFlags": [],
                "identityElements": [],
                "implementationImpact": "visual-only",
            })
            analysis["capabilityClaims"] = [
                {"capability": "realtime-presence", "status": "VERIFIED", "evidence": []}
            ]

            report = evaluate_adoption(
                root,
                "Evaluate presence",
                images=["reference.png"],
                analysis=analysis,
            )

            self.assertEqual(report["decisions"][0]["decision"], "DEFER")
            self.assertEqual(report["status"], "REVIEW_REQUIRED")
            self.assertFalse(report["implementationReady"])

    def test_bound_url_capture_can_be_evaluated_and_tampering_blocks_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_healthy_repository(root)
            capture = root / "artifacts/references/example/page.html"
            capture.parent.mkdir(parents=True)
            capture.write_text("<main>Reference capture</main>", encoding="utf-8")
            source = "https://example.com/reference"
            analysis = self._analysis_for({
                "id": "PAT-FOCUS",
                "source": source,
                "name": "Focused decision hierarchy",
                "category": "layout",
                "observation": "The decision precedes supporting detail.",
                "whyItWorks": "It lowers decision search cost.",
                "productRelevance": "The proposal has one primary decision.",
                "proposedUse": "Place the primary decision before supporting detail.",
                "keywords": ["decision hierarchy"],
                "requiredCapabilities": [],
                "riskFlags": [],
                "identityElements": [],
                "implementationImpact": "visual-only",
            })
            analysis["sourceEvidence"] = [{
                "source": source,
                "artifacts": [{
                    "kind": "dom-capture",
                    "path": capture.relative_to(root).as_posix(),
                    "sha256": hashlib.sha256(capture.read_bytes()).hexdigest(),
                }],
            }]

            report = evaluate_adoption(root, "Improve decision hierarchy", references=[source], analysis=analysis)
            self.assertEqual(report["status"], "READY")
            self.assertTrue(report["implementationReady"])

            capture.write_text("tampered", encoding="utf-8")
            blocked = evaluate_adoption(root, "Improve decision hierarchy", references=[source], analysis=analysis)
            self.assertEqual(blocked["status"], "BLOCKED")
            self.assertTrue(any("hash mismatch" in error for error in blocked["errors"]))

    def test_model_recommendation_cannot_override_deterministic_decline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Product\n", encoding="utf-8")
            image = root / "reference.png"
            image.write_bytes(
                b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 900, 600)
            )
            pattern = {
                "id": "PAT-AUTO-APPROVE",
                "source": "reference.png",
                "name": "Automatic approval",
                "category": "workflow",
                "observation": "The source auto-approves a transaction.",
                "whyItWorks": "It removes a step.",
                "productRelevance": "The quote flow contains approval.",
                "proposedUse": "Auto-approve quotes on open.",
                "keywords": ["automatic approval"],
                "requiredCapabilities": ["automatic-approval-authority"],
                "riskFlags": [],
                "identityElements": [],
                "implementationImpact": "workflow",
                "recommendedDecision": "ADOPT",
            }
            analysis = self._analysis_for(pattern)
            absence_evidence = self._write_capability_search_evidence(
                root,
                "automatic-approval-authority",
            )
            analysis["capabilityClaims"] = [{
                "capability": "automatic-approval-authority",
                "status": "ABSENT",
                "evidenceMethod": "repository-search",
                "evidence": [absence_evidence],
            }]

            report = evaluate_adoption(root, "Evaluate auto approval", images=["reference.png"], analysis=analysis)

            self.assertEqual(report["decisions"][0]["decision"], "DECLINE")
            self.assertEqual(report["status"], "DECLINED")

    def test_conflicted_design_system_defers_component_adoption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {
                "package.json": '{"dependencies":{"react":"1.0.0"}}',
                "components/Button.tsx": "export const Button = () => null;",
                "components2/Button.tsx": "export const Button = () => null;",
                "docs/design-system.md": "# Design System\nUse blue buttons.\n",
                "design/DESIGN-LANGUAGE.md": "# Design Language\nUse red buttons.\n",
                "styles/globals.css": ":root { --color-primary: blue; }",
            }
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            image = root / "reference.png"
            image.write_bytes(
                b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 900, 600)
            )
            analysis = self._analysis_for({
                "id": "PAT-CARD",
                "source": "reference.png",
                "name": "Summary card",
                "category": "component",
                "observation": "A card groups decision context.",
                "whyItWorks": "It keeps consequences near the action.",
                "productRelevance": "The product has a decision summary.",
                "proposedUse": "Adapt the summary card.",
                "keywords": ["summary card"],
                "requiredCapabilities": [],
                "riskFlags": [],
                "identityElements": [],
                "implementationImpact": "component",
            })

            report = evaluate_adoption(root, "Evaluate summary card", images=["reference.png"], analysis=analysis)

            self.assertEqual(report["decisions"][0]["decision"], "DEFER")
            self.assertEqual(report["status"], "REVIEW_REQUIRED")

    def test_unaligned_design_system_defers_component_adoption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package.json").write_text(
                '{"dependencies":{"react":"1.0.0"}}',
                encoding="utf-8",
            )
            image = root / "reference.png"
            image.write_bytes(
                b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 900, 600)
            )
            analysis = self._analysis_for({
                "id": "PAT-CARD",
                "source": "reference.png",
                "name": "Summary card",
                "category": "component",
                "observation": "A card groups decision context.",
                "whyItWorks": "It keeps consequences near the action.",
                "productRelevance": "The product has a decision summary.",
                "proposedUse": "Adapt the summary card.",
                "keywords": ["summary card"],
                "requiredCapabilities": [],
                "riskFlags": [],
                "identityElements": [],
                "implementationImpact": "component",
            })

            report = evaluate_adoption(root, "Evaluate summary card", images=["reference.png"], analysis=analysis)

            self.assertEqual(report["designSystemHealth"]["status"], "NEEDS_ALIGNMENT")
            self.assertEqual(report["decisions"][0]["decision"], "DEFER")

    def test_proposed_memory_record_does_not_become_authority_from_embedded_words(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            memory = root / ".design/memory/decisions.jsonl"
            memory.parent.mkdir(parents=True)
            memory.write_text(
                json.dumps({
                    "id": "DL-TEST-001",
                    "status": "proposed",
                    "decision": "Do not add a carousel until accepted by a human.",
                }) + "\n",
                encoding="utf-8",
            )
            image = root / "reference.png"
            image.write_bytes(
                b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 900, 600)
            )
            analysis = self._analysis_for({
                "id": "PAT-CAROUSEL",
                "source": "reference.png",
                "name": "Carousel",
                "category": "layout",
                "observation": "A carousel rotates supporting proof.",
                "whyItWorks": "It compresses optional proof.",
                "productRelevance": "The surface has optional proof.",
                "proposedUse": "Evaluate a bounded proof carousel.",
                "keywords": ["carousel"],
                "requiredCapabilities": [],
                "riskFlags": [],
                "identityElements": [],
                "implementationImpact": "visual-only",
            })

            report = evaluate_adoption(root, "Evaluate carousel", images=["reference.png"], analysis=analysis)

            self.assertNotEqual(report["decisions"][0]["decision"], "BLOCKED")
            authority = next(item for item in report["authorities"]["sources"] if item["kind"] == "design-decision")
            self.assertEqual(authority["statements"][0]["status"], "proposed")

    def test_malformed_adapter_payload_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Product\n", encoding="utf-8")
            image = root / "reference.png"
            image.write_bytes(
                b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 900, 600)
            )
            analysis = self._analysis_for({
                "id": "PAT-BAD",
                "source": "reference.png",
                "name": "Bad payload",
                "category": "unknown-category",
                "observation": "Observed.",
                "whyItWorks": "Reason.",
                "productRelevance": "Relevant.",
                "proposedUse": "Use it.",
                "implementationImpact": "database",
            })
            analysis["analyzer"]["type"] = "untrusted-agent"
            analysis["analyzer"]["observedAt"] = "yesterday"

            report = evaluate_adoption(root, "Reject malformed analysis", images=["reference.png"], analysis=analysis)

            self.assertEqual(report["status"], "BLOCKED")
            self.assertEqual(report["decisions"], [])
            self.assertGreaterEqual(len(report["errors"]), 5)

    def test_adoption_retrieves_bounded_scoped_institutional_memory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_healthy_repository(root)
            initialize_memory(root)
            image = root / "reference.png"
            image.write_bytes(
                b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 900, 600)
            )
            analysis = self._analysis_for({
                "id": "PAT-HIERARCHY",
                "source": "reference.png",
                "name": "Commercial decision hierarchy",
                "category": "layout",
                "observation": "The next commercial decision is visually primary.",
                "whyItWorks": "It improves confidence and speed.",
                "productRelevance": "QuotePilot is a transactional commercial product.",
                "proposedUse": "Prioritize the commercial next action.",
                "keywords": ["commercial", "decision"],
                "requiredCapabilities": [],
                "riskFlags": [],
                "identityElements": [],
                "implementationImpact": "visual-only",
            })

            report = evaluate_adoption(
                root,
                "Improve quote decision hierarchy",
                images=["reference.png"],
                analysis=analysis,
                profile_name="quotepilot",
                surface="Proposal review",
            )

            context = report["memoryContext"]
            self.assertEqual(context["maxRecords"], 20)
            self.assertEqual(context["product"], "quotepilot")
            self.assertEqual(context["surface"], "Proposal review")
            self.assertTrue(any(rule["id"] == "DL-PORT-001" for rule in context["inherited_rules"]))
            self.assertEqual(report["governanceConstraints"]["status"], "REQUIRED")
            self.assertFalse(report["implementationReady"])

    def test_memory_initialization_installs_adoption_schemas(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Product\n", encoding="utf-8")

            initialize_memory(root)

            for name in ("reference-analysis.schema.json", "design-adoption-report.schema.json"):
                path = root / ".design/memory/schemas" / name
                self.assertTrue(path.is_file())
                self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["type"], "object")
            installed_report_schema = json.loads(
                (root / ".design/memory/schemas/design-adoption-report.schema.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn("memoryRequired", installed_report_schema["required"])
            self.assertIn("governanceConstraints", installed_report_schema["required"])

    def test_adoption_blocks_when_indexed_memory_authority_has_drifted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_healthy_repository(root)
            initialize_memory(root, memory_only=True)
            authority = root / "docs/design-system.md"
            rules_path = root / ".design/memory/product-rules.json"
            rules = {
                "schemaVersion": 1,
                "authorityMode": "index-only",
                "sourceAuthorities": [{
                    "path": "docs/design-system.md",
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
                            "statement": "Repository design authority outranks memory summaries.",
                            "protected": True,
                            "sourceAuthority": "docs/design-system.md",
                        }],
                    }
                },
            }
            rules_path.write_text(json.dumps(rules), encoding="utf-8")
            authority.write_text("# Drifted design system\n", encoding="utf-8")

            report = evaluate_adoption(
                root,
                "Reject stale institutional memory",
                profile_name="quotepilot",
            )

            self.assertEqual(report["status"], "BLOCKED")
            self.assertEqual(report["memoryContext"]["status"], "INVALID")
            self.assertIn("Source authority hash mismatch", " ".join(report["errors"]))

    def test_adoption_audit_fails_closed_on_malformed_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_path = root / "artifacts/design/adoptions/bad/adoption-report.json"
            report_path.parent.mkdir(parents=True)
            report_path.write_text("[]", encoding="utf-8")

            audit = audit_adoption_report(root, report_path)

            self.assertEqual(audit["status"], "FAIL")
            self.assertIn("must be an object", " ".join(audit["errors"]))

    def test_adoption_audit_replays_after_checkout_relocation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            original = workspace / "original" / "product"
            relocated = workspace / "clone" / "product"
            self._write_healthy_repository(original)
            image = original / "reference.png"
            image.write_bytes(
                b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 900, 600)
            )
            analysis = self._analysis_for({
                "id": "PAT-RELOCATED",
                "source": "reference.png",
                "name": "Portable evidence hierarchy",
                "category": "layout",
                "observation": "One action precedes supporting detail.",
                "whyItWorks": "It preserves a clear decision order.",
                "productRelevance": "The product has one primary action.",
                "proposedUse": "Preserve the primary action hierarchy.",
                "keywords": ["portable evidence"],
                "requiredCapabilities": [],
                "riskFlags": [],
                "identityElements": [],
                "implementationImpact": "visual-only",
            })
            report = evaluate_adoption(
                original,
                "Verify portable adoption evidence",
                images=["reference.png"],
                analysis=analysis,
            )
            save_adoption_bundle(report, original / "artifacts/design/adoptions/portable")
            shutil.copytree(original, relocated)

            audit = audit_adoption_report(
                relocated,
                "artifacts/design/adoptions/portable/adoption-report.json",
            )

            self.assertEqual(audit["status"], "PASS", audit)
            self.assertTrue(audit["checkoutRelocated"])
            self.assertTrue(audit["warnings"])

    def test_cli_start_accepts_matching_ready_adoption_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_healthy_repository(root)
            capture = root / "artifacts/references/example/page.html"
            capture.parent.mkdir(parents=True)
            capture.write_text("<main>Reference capture</main>", encoding="utf-8")
            task = "Improve proposal decision hierarchy"
            source = "https://example.com/reference"
            analysis = self._analysis_for({
                "id": "PAT-FOCUS",
                "source": source,
                "name": "Focused decision hierarchy",
                "category": "layout",
                "observation": "The decision precedes supporting detail.",
                "whyItWorks": "It lowers decision search cost.",
                "productRelevance": "The proposal has one primary decision.",
                "proposedUse": "Place the primary decision before supporting detail.",
                "keywords": ["decision hierarchy"],
                "requiredCapabilities": [],
                "riskFlags": [],
                "identityElements": [],
                "implementationImpact": "visual-only",
            })
            analysis["sourceEvidence"] = [{
                "source": source,
                "artifacts": [{
                    "path": capture.relative_to(root).as_posix(),
                    "sha256": hashlib.sha256(capture.read_bytes()).hexdigest(),
                }],
            }]
            report = evaluate_adoption(root, task, references=[source], analysis=analysis)
            outputs = save_adoption_bundle(report, root / "artifacts/design/adoptions/proposal-hierarchy")
            contract = root / "artifacts/design/contracts/proposal-hierarchy.json"

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "design_intelligence.cli",
                    "start",
                    task,
                    "--root",
                    str(root),
                    "--reference",
                    source,
                    "--direction",
                    "recommended",
                    "--adoption-report",
                    outputs["report"],
                    "--contract-out",
                    str(contract),
                    "--format",
                    "json",
                ],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "READY_TO_IMPLEMENT")
            self.assertEqual(payload["mission"]["adoptionGate"]["status"], "READY")
            self.assertEqual(payload["workflow"]["contract"]["relevantDesignDecisions"], ["PAT-FOCUS"])
            self.assertTrue(contract.is_file())

    def test_cli_start_accepts_matching_image_adoption_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_healthy_repository(root)
            image = root / "reference.png"
            image.write_bytes(
                b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 900, 600)
            )
            task = "Improve image-backed hierarchy"
            analysis = self._analysis_for({
                "id": "PAT-IMAGE-FOCUS",
                "source": "reference.png",
                "name": "Focused hierarchy",
                "category": "layout",
                "observation": "One decision precedes supporting detail.",
                "whyItWorks": "It lowers decision search cost.",
                "productRelevance": "The workflow has one primary decision.",
                "proposedUse": "Place the decision before supporting detail.",
                "keywords": ["focused hierarchy"],
                "requiredCapabilities": [],
                "riskFlags": [],
                "identityElements": [],
                "implementationImpact": "visual-only",
            })
            report = evaluate_adoption(root, task, images=["reference.png"], analysis=analysis)
            outputs = save_adoption_bundle(report, root / "artifacts/design/adoptions/image-hierarchy")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "design_intelligence.cli",
                    "start",
                    task,
                    "--root",
                    str(root),
                    "--image",
                    "reference.png",
                    "--direction",
                    "recommended",
                    "--adoption-report",
                    outputs["report"],
                    "--format",
                    "json",
                ],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "READY_TO_IMPLEMENT")
            self.assertEqual(payload["mission"]["referenceLedger"]["entries"][0]["kind"], "image")

    def test_adoption_bundle_is_append_only_and_fails_audit_after_source_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {
                "package.json": '{"dependencies":{"react":"1.0.0"},"devDependencies":{"axe-core":"1.0.0"}}',
                "components/ui/Button.tsx": "export const Button = () => null;",
                "docs/design-system.md": "# Design System\nPreserve action hierarchy.\n",
                "styles/globals.css": ":root { --space-2: 8px; } .x { gap: var(--space-2); }",
            }
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            image = root / "reference.png"
            image.write_bytes(
                b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 1024, 768)
            )
            analysis = self._analysis_for({
                "id": "PAT-FOCUS",
                "source": "reference.png",
                "name": "Focused action hierarchy",
                "category": "layout",
                "observation": "One primary action dominates the page.",
                "whyItWorks": "It reduces competing choices.",
                "productRelevance": "The workflow has one valid next action.",
                "proposedUse": "Strengthen the existing primary action hierarchy.",
                "keywords": ["action hierarchy"],
                "requiredCapabilities": [],
                "riskFlags": [],
                "identityElements": [],
                "implementationImpact": "visual-only",
            })
            report = evaluate_adoption(
                root,
                "Strengthen action hierarchy",
                images=["reference.png"],
                analysis=analysis,
            )
            output = root / "artifacts/design/adoptions/action-hierarchy"

            outputs = save_adoption_bundle(report, output)

            self.assertTrue(Path(outputs["report"]).is_file())
            self.assertTrue(Path(outputs["contract"]).is_file())
            self.assertEqual(audit_adoption_report(root, outputs["report"])["status"], "PASS")
            with self.assertRaisesRegex(ValueError, "append-only"):
                save_adoption_bundle(report, output)

            image.write_bytes(b"changed")
            tampered = audit_adoption_report(root, outputs["report"])
            self.assertEqual(tampered["status"], "FAIL")
            self.assertTrue(any("hash mismatch" in error for error in tampered["errors"]))

    def test_adoption_audit_detects_authority_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_healthy_repository(root)
            image = root / "reference.png"
            image.write_bytes(
                b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 1024, 768)
            )
            analysis = self._analysis_for({
                "id": "PAT-FOCUS",
                "source": "reference.png",
                "name": "Focused hierarchy",
                "category": "layout",
                "observation": "One action is visually primary.",
                "whyItWorks": "It reduces decision search cost.",
                "productRelevance": "The surface has one next action.",
                "proposedUse": "Strengthen the primary action hierarchy.",
                "keywords": ["action hierarchy"],
                "requiredCapabilities": [],
                "riskFlags": [],
                "identityElements": [],
                "implementationImpact": "visual-only",
            })
            report = evaluate_adoption(root, "Strengthen hierarchy", images=["reference.png"], analysis=analysis)
            outputs = save_adoption_bundle(report, root / "artifacts/design/adoptions/hierarchy")
            authority = root / "docs/design-system.md"

            authority.write_text("# Design System\nChanged authority.\n", encoding="utf-8")
            audit = audit_adoption_report(root, outputs["report"])

            self.assertEqual(audit["status"], "FAIL")
            self.assertTrue(any("authority" in error and "hash mismatch" in error for error in audit["errors"]))

    def test_url_capture_path_escape_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            (root / "README.md").write_text("# Product\n", encoding="utf-8")
            external = Path(outside) / "capture.html"
            external.write_text("outside", encoding="utf-8")
            source = "https://example.com/reference"
            analysis = self._analysis_for({
                "id": "PAT-NAV",
                "source": source,
                "name": "Compact navigation",
                "category": "navigation",
                "observation": "A compact rail preserves width.",
                "whyItWorks": "It preserves workspace space.",
                "productRelevance": "The product has a dense workspace.",
                "proposedUse": "Evaluate compact navigation.",
                "keywords": ["compact navigation"],
                "requiredCapabilities": [],
                "riskFlags": [],
                "identityElements": [],
                "implementationImpact": "visual-only",
            })
            analysis["sourceEvidence"] = [{
                "source": source,
                "artifacts": [{
                    "path": str(external),
                    "sha256": hashlib.sha256(external.read_bytes()).hexdigest(),
                }],
            }]

            report = evaluate_adoption(root, "Evaluate navigation", references=[source], analysis=analysis)

            self.assertEqual(report["status"], "BLOCKED")
            self.assertTrue(any("escapes repository root" in error for error in report["errors"]))

    def test_cli_adopt_accepts_a_url_and_saves_an_analysis_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Product\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "design_intelligence.cli",
                    "adopt",
                    "Evaluate a compact navigation reference",
                    "--root",
                    str(root),
                    "--reference",
                    "https://example.com/reference",
                    "--save",
                    "--format",
                    "json",
                ],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = __import__("json").loads(result.stdout)
            self.assertEqual(payload["status"], "RESEARCH_REQUIRED")
            self.assertTrue(Path(payload["saved"]["analysisRequest"]).is_file())
            self.assertFalse((root / ".design/baselines").exists())

    def _analysis_for(self, pattern: dict[str, object]) -> dict[str, object]:
        return self._analysis_for_patterns([pattern])

    def _write_capability_search_evidence(
        self,
        root: Path,
        capability: str,
    ) -> dict[str, str]:
        path = root / "artifacts/design/capability-search" / f"{capability}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({
                "schemaVersion": 1,
                "kind": "repository-search",
                "capability": capability,
                "status": "ABSENT",
                "repositoryRoot": str(root.resolve()),
                "scope": "repository",
                "queries": [capability, capability.replace("-", " ")],
                "matches": [],
            }),
            encoding="utf-8",
        )
        return {
            "path": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    def _analysis_for_patterns(self, patterns: list[dict[str, object]]) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "analyzer": {
                "type": "model",
                "name": "test-vision-adapter",
                "observedAt": "2026-08-23T12:00:00Z",
            },
            "capabilityClaims": [],
            "patterns": patterns,
        }

    def _write_healthy_repository(self, root: Path) -> None:
        files = {
            "package.json": '{"dependencies":{"react":"1.0.0"},"devDependencies":{"axe-core":"1.0.0"}}',
            "components/ui/Button.tsx": "export const Button = () => null;",
            "docs/design-system.md": "# Design System\nPreserve action hierarchy.\n",
            "styles/globals.css": ":root { --space-2: 8px; } .x { gap: var(--space-2); }",
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
