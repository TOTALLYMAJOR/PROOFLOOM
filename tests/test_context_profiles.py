from __future__ import annotations

import unittest
from pathlib import Path

from design_intelligence.context import build_context


FIXTURES = Path(__file__).parent / "fixtures"


class ContextProfileTests(unittest.TestCase):
    def test_quotepilot_context_emphasizes_numeric_clarity(self) -> None:
        report = build_context(str(FIXTURES / "mature-repo"), "quotepilot")
        self.assertTrue(any("numeric clarity" in item.lower() for item in report.validation_focus))

    def test_quietpilot_context_emphasizes_blockers_and_readiness(self) -> None:
        report = build_context(str(FIXTURES / "mature-repo"), "quietpilot")
        joined = " ".join(report.validation_focus).lower()
        self.assertIn("blockers", joined)
        self.assertIn("readiness", joined)

    def test_leaguepilot_context_emphasizes_mobile_glanceability(self) -> None:
        report = build_context(str(FIXTURES / "mature-repo"), "leaguepilot")
        joined = " ".join(report.validation_focus).lower()
        self.assertIn("mobile", joined)
        self.assertIn("glanceability", joined)


if __name__ == "__main__":
    unittest.main()
