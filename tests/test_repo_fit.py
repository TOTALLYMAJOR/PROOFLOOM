from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from design_intelligence.assessment import assess_repository
from design_intelligence.models import Presence, Recommendation, RepositoryMaturity, StructureRisk
from design_intelligence.repository import inspect_repository


FIXTURES = Path(__file__).parent / "fixtures"


class RepoFitTests(unittest.TestCase):
    def test_mature_repo_preserves_existing_authorities(self) -> None:
        assessment = assess_repository(str(FIXTURES / "mature-repo"))
        snapshot = assessment.snapshot

        self.assertEqual(snapshot.repository_maturity, RepositoryMaturity.ESTABLISHED)
        self.assertEqual(snapshot.design_documentation.status, Presence.PRESENT)
        self.assertEqual(snapshot.existing_design_skills.status, Presence.NONE)
        self.assertEqual(assessment.recommendation, Recommendation.INTEGRATE)
        self.assertEqual(assessment.structure_risk, StructureRisk.KEEP)
        self.assertEqual(assessment.runtime_strategy.value, "KEEP")
        self.assertEqual(assessment.migrate, [])
        self.assertIn("existing design decision memory", assessment.preserve)

    def test_partial_repo_prefers_alignment_not_runtime_migration(self) -> None:
        assessment = assess_repository(str(FIXTURES / "partial-repo"))

        self.assertEqual(assessment.snapshot.repository_maturity, RepositoryMaturity.PARTIAL)
        self.assertEqual(assessment.structure_risk, StructureRisk.ALIGN)
        self.assertEqual(assessment.runtime_strategy.value, "KEEP")
        self.assertIn("canonical design-language authority", assessment.add)

    def test_greenfield_repo_uses_add_recommendation(self) -> None:
        assessment = assess_repository(str(FIXTURES / "greenfield-empty"))

        self.assertEqual(assessment.snapshot.repository_maturity, RepositoryMaturity.GREENFIELD)
        self.assertEqual(assessment.recommendation, Recommendation.ADD)
        self.assertEqual(assessment.runtime_strategy.value, "KEEP")

    def test_dual_design_system_repo_requires_convergence(self) -> None:
        assessment = assess_repository(str(FIXTURES / "dual-design-system"))
        snapshot = inspect_repository(str(FIXTURES / "dual-design-system"))

        self.assertEqual(assessment.structure_risk, StructureRisk.CONVERGE)
        self.assertTrue(any(item.capability == "design_language" for item in snapshot.semantic_duplicates))
        self.assertTrue(any(item.capability == "component_system" for item in snapshot.semantic_duplicates))
        self.assertIn("design language", assessment.migrate)
        self.assertIn("component system", assessment.migrate)

    def test_refactor_risk_repo_can_recommend_align_without_runtime_restructure(self) -> None:
        assessment = assess_repository(str(FIXTURES / "refactor-risk-repo"))

        self.assertEqual(assessment.structure_risk, StructureRisk.ALIGN)
        self.assertEqual(assessment.runtime_strategy.value, "KEEP")
        self.assertTrue(
            any("runtime restructure is not justified" in note.lower() for note in assessment.notes)
        )

    def test_playwright_dependency_is_not_reported_as_cypress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                json.dumps({"devDependencies": {"@playwright/test": "1.62.1"}}),
                encoding="utf-8",
            )
            snapshot = inspect_repository(root)
            self.assertNotEqual(snapshot.playwright.status, Presence.NONE)
            self.assertEqual(snapshot.cypress.status, Presence.NONE)


if __name__ == "__main__":
    unittest.main()
