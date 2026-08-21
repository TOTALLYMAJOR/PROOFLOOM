from __future__ import annotations

import unittest

from design_intelligence.references import analyze_references


class ReferenceTests(unittest.TestCase):
    def test_reference_analysis_transforms_instead_of_cloning(self) -> None:
        report = analyze_references(
            [
                {
                    "source": "Refero / checkout example",
                    "observed_patterns": ["Tight summary rail with explicit next step"],
                    "strengths": ["clear progression"],
                    "risks": ["generic ecommerce styling"]
                }
            ],
            "quotepilot",
        )

        self.assertEqual(report.overall_clone_risk, "LOW")
        transformed = " ".join(report.transformations[0].adapt).lower()
        self.assertIn("build -> decide -> book", transformed)
        self.assertNotIn("copy the same", transformed)

    def test_cloney_reference_is_flagged(self) -> None:
        report = analyze_references(
            [
                {
                    "source": "Competitor screenshot",
                    "observed_patterns": ["Copy the same layout and same palette"],
                    "strengths": ["high polish"],
                    "risks": ["clone the source brand"]
                }
            ],
            "leaguepilot",
        )

        self.assertEqual(report.overall_clone_risk, "HIGH")
        self.assertLess(report.transformations[0].score, 5)


if __name__ == "__main__":
    unittest.main()
