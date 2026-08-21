from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from design_intelligence.evidence import build_evidence_pack, write_evidence_pack
from design_intelligence.linting import run_lint
from design_intelligence.reviewing import review_manifest
from design_intelligence.validation import validate_repository


FIXTURES = Path(__file__).parent / "fixtures"


class LintReviewValidationTests(unittest.TestCase):
    def test_design_linter_catches_duplicate_primitives_and_accessibility_drift(self) -> None:
        report = run_lint(str(FIXTURES / "dual-design-system"))
        rule_ids = {finding.rule_id for finding in report.findings}

        self.assertEqual(report.status.value, "FAIL")
        self.assertIn("component-duplicate-primitive", rule_ids)
        self.assertIn("a11y-image-alt", rule_ids)
        self.assertIn("a11y-icon-button-name", rule_ids)
        self.assertIn("layout-unsafe-width", rule_ids)

    def test_visual_review_can_fail_even_when_styling_is_coherent(self) -> None:
        manifest = json.loads((FIXTURES / "broken-ia" / "review-manifest.json").read_text(encoding="utf-8"))
        report = review_manifest(manifest)

        self.assertEqual(report.verdict.value, "FAIL")
        self.assertEqual({finding.root_cause for finding in report.findings}, {"hierarchy", "workflow"})

    def test_validate_can_write_evidence_pack(self) -> None:
        manifest = json.loads((FIXTURES / "broken-ia" / "review-manifest.json").read_text(encoding="utf-8"))
        report = validate_repository(str(FIXTURES / "broken-ia"), manifest)
        pack = build_evidence_pack(report.assessment, report, review_manifest=manifest)

        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "evidence-pack.md"
            write_evidence_pack(pack, output)
            content = output.read_text(encoding="utf-8")

        self.assertEqual(report.status.value, "FAIL")
        self.assertIn("Evidence Pack", content)
        self.assertIn("Decision summary", content)


if __name__ == "__main__":
    unittest.main()
