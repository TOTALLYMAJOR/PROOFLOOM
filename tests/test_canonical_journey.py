from __future__ import annotations

import unittest
from pathlib import Path

from design_intelligence.control_plane import program_status, run_control_plane_doctor
from design_intelligence.governance import audit_governance


ROOT = Path(__file__).resolve().parents[1]


class CanonicalJourneyTests(unittest.TestCase):
    def test_adoption_journey_is_canonical_bound_and_executable(self) -> None:
        audit = audit_governance(ROOT)
        journey = audit["journeyModel"]

        self.assertEqual(journey["status"], "DEFINED", audit)
        self.assertEqual(journey["proofStatus"], "LINKED", audit)
        self.assertIn("tests/test_canonical_journey.py", journey["linkedTests"])
        self.assertNotIn(
            "MISSING-CANONICAL-JOURNEY",
            {finding["id"] for finding in audit["findings"]},
        )
        self.assertNotIn(
            "JOURNEY-PROOF-FRAGMENTED",
            {finding["id"] for finding in audit["findings"]},
        )

        doctor = run_control_plane_doctor(ROOT)
        self.assertEqual(doctor["status"], "PASS", doctor)

        program = program_status(ROOT)
        self.assertEqual(program["status"], "IN_PROGRESS", program)
        self.assertFalse(program["completionClaimed"])
        self.assertGreater(program["backlog"]["open"], 0)


if __name__ == "__main__":
    unittest.main()
