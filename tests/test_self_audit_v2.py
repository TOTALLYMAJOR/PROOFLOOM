from __future__ import annotations

import unittest
from pathlib import Path

from design_intelligence.self_audit import run_self_audit


ROOT = Path(__file__).resolve().parents[1]


class SelfAuditV2Tests(unittest.TestCase):
    def test_repository_self_audit_passes_after_exact_authority_ratification(self) -> None:
        report = run_self_audit(ROOT)

        self.assertEqual(report["status"], "PASS", report)
        self.assertNotIn("governanceConvergence", report["failures"])
        self.assertEqual(report["checks"]["designAdoptions"]["status"], "PASS")
        self.assertEqual(report["checks"]["repairCycles"]["count"], 3)
        self.assertEqual(report["checks"]["quality"]["score"], 100)
        self.assertEqual(report["checks"]["baselines"]["checked"], 5)
        self.assertEqual(report["checks"]["architectureGraph"]["status"], "PASS")
        self.assertFalse(report["checks"]["architectureGraph"]["truncated"])
        self.assertEqual(report["checks"]["governanceConvergence"]["status"], "PASS")
        self.assertEqual(
            report["checks"]["governanceConvergence"]["authorityDrift"]["status"],
            "STABLE",
        )
        self.assertFalse(
            report["checks"]["governanceConvergence"]["finalizationReadiness"]["completionClaimed"]
        )


if __name__ == "__main__":
    unittest.main()
