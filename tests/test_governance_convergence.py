from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from design_intelligence.cli import main as design_intelligence_main
from design_intelligence.control_plane import build_manifest
from design_intelligence.governance import (
    ADAPTER_PATH,
    MANIFEST_PATH,
    MAP_PATH,
    PLAN_PATH,
    RATIFICATION_PATH,
    READOUT_PATH,
    apply_governance_convergence,
    audit_governance,
    governance_design_preflight,
    verify_governance_convergence,
)


class GovernanceConvergenceTests(unittest.TestCase):
    def test_mature_repository_maps_understanding_and_preserves_existing_backlog(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._mature_repository(Path(temporary))

            audit = audit_governance(root)
            manifest = build_manifest(root)

            self.assertEqual(audit["status"], "READY", audit)
            self.assertEqual(audit["journeyModel"]["status"], "DEFINED")
            self.assertEqual(audit["journeyModel"]["proofStatus"], "LINKED")
            self.assertEqual(audit["backlogModel"]["itemCount"], 1)
            self.assertEqual(audit["backlogModel"]["counts"]["ACTIVE"], 1)
            self.assertEqual(audit["finalizationReadiness"]["status"], "DESIGN_READY")
            self.assertEqual(audit["designGate"]["status"], "READY")
            backlog_paths = [
                item["path"]
                for item in manifest["spec"]["planes"]["intent"]["backlog"]["sources"]
            ]
            self.assertEqual(backlog_paths, ["docs/backlog-now.md"])
            self.assertIn("apps/**", manifest["spec"]["planes"]["architecture"]["impactGraph"]["include"])
            self.assertIn("packages/**", manifest["spec"]["planes"]["architecture"]["impactGraph"]["include"])

    def test_broken_journey_command_and_incomplete_atlas_lock_design(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._mature_repository(Path(temporary), create_e2e=False)
            self._write(root / "docs/atlas/atlas-manifest.yaml", "remaining_prompt_range: QP-02..QP-18\n")
            self._write(root / "docs/atlas/00-governance/source-authority.md", "# Source Authority\n")
            self._write(root / "docs/atlas/04-workflows/workflow-register.yaml", "status: active\n")
            self._write(root / "docs/atlas/10-design-system/component-register.yaml", "status: active\n")

            audit = audit_governance(root)

            finding_ids = {item["id"] for item in audit["findings"]}
            self.assertIn("BROKEN-SCRIPT-test-e2e-product", finding_ids)
            self.assertIn("INCOMPLETE-ENTERPRISE-ATLAS", finding_ids)
            self.assertEqual(audit["journeyModel"]["proofStatus"], "MISSING")
            self.assertEqual(audit["designGate"]["status"], "LOCKED")
            self.assertEqual(audit["finalizationReadiness"]["status"], "UNDERSTANDING_INCOMPLETE")

    def test_unrelated_e2e_wrapper_cannot_link_canonical_journey_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._mature_repository(Path(temporary), create_e2e=False)
            journey = root / "docs/architecture/mvp-golden-path.md"
            journey.write_text(
                "# MVP Golden Path\n\nAuthority: canonical journeys\n\n"
                "`Inquiry -> Decision -> Completion`\n",
                encoding="utf-8",
            )
            self._write(root / "scripts/run-product-smoke.mjs", "// executable journey wrapper\n")
            package = json.loads((root / "package.json").read_text(encoding="utf-8"))
            package["scripts"]["test:e2e:product"] = "node scripts/run-product-smoke.mjs"
            (root / "package.json").write_text(json.dumps(package), encoding="utf-8")

            audit = audit_governance(root)

            self.assertEqual(audit["journeyModel"]["proofStatus"], "MISSING", audit)
            self.assertEqual(audit["journeyModel"]["linkedTests"], [])
            self.assertEqual(audit["designGate"]["status"], "LOCKED")

    def test_feature_journey_fragments_do_not_define_a_canonical_product_journey(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._mature_repository(Path(temporary))
            self._write(
                root / "docs/architecture/mvp-golden-path.md",
                "# Attendance Workflow\n\n"
                "This feature preserves canonical pricing; it is not the product journey authority.\n\n"
                "`Draft -> Confirm -> Complete`\n\n"
                "Proof: `e2e/product-journey.spec.ts`\n",
            )

            audit = audit_governance(root)

            self.assertEqual(audit["journeyModel"]["status"], "PARTIAL", audit)
            self.assertEqual(audit["journeyModel"]["bindingJourneyCount"], 0)
            self.assertIn(
                "MISSING-CANONICAL-JOURNEY",
                {item["id"] for item in audit["findings"]},
            )
            self.assertEqual(audit["finalizationReadiness"]["understanding"], "INCOMPLETE")
            self.assertEqual(audit["designGate"]["status"], "LOCKED")

    def test_repository_native_canonical_index_binds_linked_journey_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._mature_repository(Path(temporary))
            (root / "docs/architecture/mvp-golden-path.md").unlink()
            self._write(
                root / "docs/PRODUCT_INTELLIGENCE.md",
                "# Product Intelligence\n\n"
                "This is the canonical entry point for deciding whether the product creates value.\n\n"
                "## Required artifacts\n\n"
                "| Artifact | Governing question |\n|---|---|\n"
                "| [User Journey](product-intelligence/USER_JOURNEY_FUNNELS.md) "
                "| Where does value creation succeed or fail? |\n"
                "| [Success Metrics](product-intelligence/SUCCESS_METRICS.md) "
                "| Which measures distinguish value from activity? |\n",
            )
            self._write(
                root / "docs/product-intelligence/USER_JOURNEY_FUNNELS.md",
                "# User Journey and Funnel Model\n\nStatus: mixed evidence.\n\n"
                "`Intent -> Commitment -> Fulfillment`\n\n"
                "Proof: `e2e/product-journey.spec.ts`\n",
            )
            self._write(
                root / "docs/product-intelligence/SUCCESS_METRICS.md",
                "# Success Metrics\n\nMET-01 measures a governed outcome.\n",
            )

            audit = audit_governance(root)

            self.assertEqual(audit["journeyModel"]["status"], "DEFINED", audit)
            self.assertEqual(audit["journeyModel"]["proofStatus"], "LINKED", audit)
            binding_sources = {
                item["source"]
                for item in audit["journeyModel"]["journeys"]
                if item["binding"]
            }
            self.assertEqual(
                binding_sources,
                {"docs/product-intelligence/USER_JOURNEY_FUNNELS.md"},
            )
            index = next(
                item for item in audit["authorities"]
                if item["path"] == "docs/PRODUCT_INTELLIGENCE.md"
            )
            self.assertIn("journeys", index["declaredAuthorityRoles"])
            self.assertIn("metrics", index["declaredAuthorityRoles"])

            apply_governance_convergence(root)
            self._write(
                root / "docs/product-intelligence/SUCCESS_METRICS.md",
                "# Success Metrics\n\nMET-01 now has a materially different definition.\n",
            )
            verification = verify_governance_convergence(root)
            self.assertEqual(verification["status"], "FAIL", verification)
            self.assertIn(
                "docs/product-intelligence/SUCCESS_METRICS.md",
                verification["authorityDrift"]["changed"],
            )

    def test_nested_package_script_resolves_parent_relative_target_from_package_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._mature_repository(Path(temporary))
            self._write(root / "scripts/check-foundation.mjs", "// repository check\n")
            self._write(
                root / "functions-connect/package.json",
                json.dumps({"scripts": {"check": "node ../scripts/check-foundation.mjs"}}),
            )

            audit = audit_governance(root)

            self.assertEqual(audit["scriptDamage"], [], audit)

    def test_dev_tasks_is_recognized_as_an_existing_backlog_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._mature_repository(Path(temporary))
            (root / "docs/backlog-now.md").unlink()
            self._write(
                root / "DEV_TASKS.md",
                "# Development Tasks\n\n"
                "This file contains open work only and is the prioritized backlog.\n\n"
                "## P0\n\n- [ ] Complete the governed local pilot.\n",
            )

            audit = audit_governance(root)

            self.assertEqual(audit["backlogModel"]["status"], "MAPPED", audit)
            self.assertEqual(audit["backlogModel"]["activeSources"], ["DEV_TASKS.md"])
            self.assertNotIn("MISSING-BACKLOG", {item["id"] for item in audit["findings"]})

    def test_backlog_projection_prefers_active_items_and_keeps_unique_table_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._mature_repository(Path(temporary))
            self._write(
                root / "docs/backlog-next.md",
                "# Next\n\n"
                "### WORK-001: Staged pointer\n\n- Classification: planned\n\n"
                "| Item | Verification outcome |\n"
                "| --- | --- |\n"
                "| WORK-002 | Complete the staged customer proof |\n",
            )

            audit = audit_governance(root)

            backlog = audit["backlogModel"]
            self.assertEqual(backlog["itemCount"], 2, backlog)
            self.assertEqual({item["id"] for item in backlog["items"]}, {"WORK-001", "WORK-002"})
            self.assertEqual(backlog["shadowedRecords"], [{
                "id": "WORK-001",
                "source": "docs/backlog-next.md",
                "shadowedBy": "docs/backlog-now.md",
            }])

    def test_apply_writes_only_derived_bindings_and_detects_later_vision_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._mature_repository(Path(temporary))
            vision = root / "docs/product/product-vision.md"
            original = vision.read_text(encoding="utf-8")

            first = apply_governance_convergence(root)
            second = apply_governance_convergence(root)

            self.assertEqual(first["status"], "APPLIED_READY", first)
            self.assertEqual(
                set(first["writes"]),
                {MAP_PATH, ADAPTER_PATH, MANIFEST_PATH, READOUT_PATH, PLAN_PATH, RATIFICATION_PATH},
            )
            self.assertEqual(second["writes"], [])
            self.assertFalse(first["canonicalAuthoritiesModified"])
            self.assertEqual(vision.read_text(encoding="utf-8"), original)
            self.assertEqual(verify_governance_convergence(root)["status"], "PASS")

            vision.write_text("# Product Vision\n\nThe agent silently changed the product promise.\n", encoding="utf-8")
            drift = verify_governance_convergence(root)

            self.assertEqual(drift["status"], "FAIL")
            self.assertEqual(drift["authorityDrift"]["status"], "DRIFT_DETECTED")
            self.assertIn("docs/product/product-vision.md", drift["authorityDrift"]["changed"])
            with self.assertRaisesRegex(ValueError, "cannot be rebaselined"):
                apply_governance_convergence(root)

            receipt_path = root / ".dev/governance/owner-authority-drift-receipt.json"
            self._write(
                receipt_path,
                json.dumps({
                    "kind": "AuthorityDriftRatification",
                    "decision": "ACCEPT_AUTHORITY_DRIFT",
                    "authority": "repository-owner",
                    "approvedBy": "fixture-owner",
                    "approvedAt": "2026-08-23T12:00:00+00:00",
                    "reason": "Accept the fixture vision change for this ratification test.",
                    "paths": drift["authorityDrift"]["changed"],
                    "authorityStateSha256": drift["authorityDrift"]["currentAuthorityStateSha256"],
                }),
            )
            accepted = apply_governance_convergence(root, ratification_path=receipt_path)
            self.assertEqual(accepted["status"], "APPLIED_READY", accepted)
            self.assertEqual(verify_governance_convergence(root)["status"], "PASS")

    def test_untracked_skill_is_reported_but_not_promoted_to_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._mature_repository(Path(temporary))
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            self._write(root / ".agents/skills/design-language/SKILL.md", "# Untracked design skill\n")

            audit = audit_governance(root)

            paths = [item["path"] for item in audit["untrackedAuthorityCandidates"]]
            self.assertEqual(paths, [".agents/skills/design-language/SKILL.md"])
            self.assertNotIn(
                ".agents/skills/design-language/SKILL.md",
                [item["path"] for item in audit["authorities"]],
            )
            self.assertEqual(audit["designGate"]["status"], "LOCKED")

    def test_untracked_product_intelligence_authority_locks_design(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._mature_repository(Path(temporary))
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            self._write(
                root / "docs/product-intelligence/USER_JOURNEY_FUNNELS.md",
                "# User Journey and Funnel Model\n\nAuthority: canonical journeys\n\n"
                "`Intent -> Commitment -> Fulfillment`\n",
            )
            self._write(
                root / "docs/product-intelligence/BASELINES_AND_TARGETS.md",
                "# Baselines and Targets\n\nProduction baselines remain uncollected.\n",
            )
            self._write(
                root / "docs/product-intelligence/QUALITY_GUARDRAILS.md",
                "# Quality Guardrails\n\nUnsafe states stop release.\n",
            )

            audit = audit_governance(root)

            self.assertTrue(
                {
                    "docs/product-intelligence/BASELINES_AND_TARGETS.md",
                    "docs/product-intelligence/QUALITY_GUARDRAILS.md",
                    "docs/product-intelligence/USER_JOURNEY_FUNNELS.md",
                }.issubset({item["path"] for item in audit["untrackedAuthorityCandidates"]}),
                audit,
            )
            self.assertIn("UNTRACKED-AUTHORITY", {item["id"] for item in audit["findings"]})
            self.assertEqual(audit["designGate"]["status"], "LOCKED")

    def test_added_critical_authority_invalidates_applied_convergence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._mature_repository(Path(temporary))
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            apply_governance_convergence(root)
            self._write(
                root / "docs/product-intelligence/USER_JOURNEY_FUNNELS.md",
                "# User Journey and Funnel Model\n\nAuthority: canonical journeys\n\n"
                "`Intent -> Commitment -> Fulfillment`\n",
            )
            subprocess.run(
                ["git", "add", "docs/product-intelligence/USER_JOURNEY_FUNNELS.md"],
                cwd=root,
                check=True,
            )

            verification = verify_governance_convergence(root)

            self.assertEqual(verification["status"], "FAIL", verification)
            self.assertEqual(verification["authorityDrift"]["status"], "DRIFT_DETECTED")
            self.assertEqual(
                verification["authorityDrift"]["added"],
                ["docs/product-intelligence/USER_JOURNEY_FUNNELS.md"],
            )

    def test_design_front_door_blocks_an_unresolved_repository_in_plain_language(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write(root / "README.md", "# Unfinished product\n")
            self._write(root / "docs/atlas/atlas-manifest.yaml", "remaining_prompt_range: QP-02..QP-18\n")
            self._write(root / "docs/atlas/00-governance/source-authority.md", "# Source Authority\n")
            self._write(root / "docs/atlas/04-workflows/workflow-register.yaml", "status: active\n")
            self._write(root / "docs/atlas/10-design-system/component-register.yaml", "status: active\n")
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                exit_code = design_intelligence_main([
                    "start", str(root), "Redesign the product", "--format", "text"
                ])

            self.assertEqual(exit_code, 1)
            self.assertIn("DESIGN IS LOCKED", output.getvalue())
            self.assertEqual(governance_design_preflight(root)["status"], "BLOCKED")

    def test_apply_refuses_to_overwrite_a_repository_owned_governance_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._mature_repository(Path(temporary))
            protected = root / ADAPTER_PATH
            self._write(protected, '{"owner":"repository"}\n')

            with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
                apply_governance_convergence(root)

            self.assertEqual(protected.read_text(encoding="utf-8"), '{"owner":"repository"}\n')

    def test_missing_applied_manifest_locks_design_instead_of_returning_to_advisory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._mature_repository(Path(temporary))
            apply_governance_convergence(root)
            (root / MANIFEST_PATH).unlink()

            preflight = governance_design_preflight(root)

            self.assertEqual(preflight["status"], "BLOCKED")
            self.assertEqual(preflight["enforcementMode"], "APPLIED_CONVERGENCE")
            self.assertIn(
                f"Missing generated governance artifact: {MANIFEST_PATH}",
                preflight["errors"],
            )

    def _mature_repository(self, root: Path, *, create_e2e: bool = True) -> Path:
        self._write(root / "AGENTS.md", "# Repository Instructions\n\nThis is the governing agent contract.\n")
        self._write(
            root / "docs/product/product-vision.md",
            "# Product Vision\n\nThe canonical product vision is to finish one reliable customer journey.\n",
        )
        self._write(
            root / "docs/product/platform-specification.md",
            "# Product Requirements\n\nStatus: active\n\nThe user must complete the product journey.\n",
        )
        self._write(
            root / "docs/architecture/mvp-golden-path.md",
            "# MVP Golden Path\n\nAuthority: canonical journeys\n\n"
            "`Inquiry -> Decision -> Completion`\n\n"
            "Proof: `e2e/product-journey.spec.ts`\n",
        )
        self._write(
            root / "docs/architecture/adr/0001-architecture.md",
            "# ADR-0001\n\nStatus: accepted\n\nUse a modular application.\n",
        )
        self._write(
            root / "docs/backlog-now.md",
            "# Backlog Now\n\n### WORK-001: Finish the product journey\n\n"
            "- Status: ACTIVE\n"
            "- Outcome: the user completes the journey reliably.\n"
            "- Success signal: the end-to-end proof passes.\n"
            "- Evidence or assumption: evidence from the governed journey test.\n",
        )
        self._write(root / "apps/web/page.tsx", "export default function Page() { return null; }\n")
        self._write(root / "packages/domain/index.ts", "export const truth = true;\n")
        if create_e2e:
            self._write(root / "e2e/product-journey.spec.ts", "// journey proof\n")
        self._write(
            root / "package.json",
            json.dumps({
                "workspaces": ["apps/*", "packages/*"],
                "scripts": {
                    "test:e2e:product": "playwright test e2e/product-journey.spec.ts",
                    "test": "node --test",
                },
            }),
        )
        return root

    def _write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
