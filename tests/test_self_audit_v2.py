from __future__ import annotations

import unittest
from pathlib import Path

from design_intelligence.self_audit import run_self_audit


ROOT = Path(__file__).resolve().parents[1]


class SelfAuditV2Tests(unittest.TestCase):
    def test_repository_self_audit_passes_with_three_repair_proofs(self) -> None:
        report = run_self_audit(ROOT)

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["checks"]["repairCycles"]["count"], 3)
        self.assertEqual(report["checks"]["quality"]["score"], 100)
        self.assertEqual(report["checks"]["baselines"]["checked"], 5)
        self.assertEqual(report["checks"]["architectureGraph"]["status"], "PASS")
        self.assertFalse(report["checks"]["architectureGraph"]["truncated"])


if __name__ == "__main__":
    unittest.main()
