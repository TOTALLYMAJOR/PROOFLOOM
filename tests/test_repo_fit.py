from __future__ import annotations

import unittest
from pathlib import Path

from repo_fit.assess import assess_repository
from repo_fit.inspect import inspect_repository
from repo_fit.models import Presence, Recommendation, RepositoryMaturity, Strategy, StructureRisk


FIXTURES = Path(__file__).parent / "fixtures"


class RepoFitTests(unittest.TestCase):
    def test_established_nextjs_fixture(self) -> None:
        assessment = assess_repository(FIXTURES / "established-nextjs")
        snapshot = assessment.snapshot

        self.assertEqual(snapshot.frontend, "Next.js")
        self.assertEqual(snapshot.styling, "Tailwind")
        self.assertEqual(snapshot.component_system, "shadcn + local primitives")
        self.assertEqual(snapshot.repository_maturity, RepositoryMaturity.ESTABLISHED)
        self.assertEqual(assessment.recommendation, Recommendation.INTEGRATE)
        self.assertEqual(assessment.structure_risk, StructureRisk.ALIGN)
        self.assertEqual(assessment.runtime_strategy, Strategy.PRESERVE)
        self.assertIn("current runtime scaffold", assessment.preserve)

    def test_partial_repo_prefers_knowledge_alignment(self) -> None:
        assessment = assess_repository(FIXTURES / "partial-react")
        snapshot = assessment.snapshot

        self.assertEqual(snapshot.frontend, "React")
        self.assertEqual(snapshot.repository_maturity, RepositoryMaturity.PARTIAL)
        self.assertEqual(assessment.structure_risk, StructureRisk.KEEP)
        self.assertEqual(assessment.knowledge_strategy, Strategy.ALIGN)
        self.assertEqual(assessment.runtime_strategy, Strategy.PRESERVE)
        self.assertIn("product design profile", assessment.add)

    def test_conflicted_repo_flags_convergence(self) -> None:
        snapshot = inspect_repository(FIXTURES / "conflicted-frontend")
        assessment = assess_repository(FIXTURES / "conflicted-frontend")

        self.assertEqual(snapshot.design_documentation.status, Presence.PARTIAL)
        self.assertEqual(assessment.structure_risk, StructureRisk.CONVERGE)
        self.assertEqual(assessment.knowledge_strategy, Strategy.CONVERGE)
        self.assertEqual(assessment.recommendation, Recommendation.INTEGRATE)
        self.assertTrue(any("dual design authority" in note.lower() for note in assessment.notes))


if __name__ == "__main__":
    unittest.main()
