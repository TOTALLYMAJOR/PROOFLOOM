from __future__ import annotations

import json
import unittest
from importlib.resources import files
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ClaimBoundaryRegistrySchemaTests(unittest.TestCase):
    def test_schema_is_bundled_with_quietpilot_derived_fields(self) -> None:
        schema = json.loads(
            files("design_intelligence")
            .joinpath("data/schemas/claim-boundary-registry.schema.json")
            .read_text(encoding="utf-8")
        )

        self.assertEqual(schema["properties"]["schemaVersion"]["const"], 1)
        claim_required = set(schema["$defs"]["claimBoundary"]["required"])
        self.assertTrue(
            {
                "claim",
                "requiredEvidence",
                "allowedWording",
                "forbiddenWording",
                "affectedSurfaces",
                "visibility",
                "requiredGuards",
                "riskIfViolated",
            }
            <= claim_required
        )
        surface_required = set(schema["$defs"]["statefulSurfaceContract"]["required"])
        self.assertTrue(
            {
                "stage",
                "knownTruth",
                "missingOrBlocked",
                "proofBoundary",
                "nextActionOwner",
                "nextAction",
                "forbiddenInference",
            }
            <= surface_required
        )

    def test_fixture_exercises_claim_boundaries_and_stateful_surface_contracts(self) -> None:
        fixture = json.loads(
            (ROOT / "tests/fixtures/claim-boundary-registry.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(fixture["schemaVersion"], 1)
        self.assertEqual(fixture["status"], "active")
        claim_ids = []
        for family in fixture["claimFamilies"]:
            for claim in family["claims"]:
                claim_ids.append(f"{family['id']}.{claim['id']}")
                self.assertTrue(claim["requiredEvidence"])
                self.assertTrue(claim["allowedWording"])
                self.assertTrue(claim["forbiddenWording"])
                self.assertTrue(claim["affectedSurfaces"])
                self.assertTrue(claim["visibility"])
                self.assertTrue(claim["riskIfViolated"])
                forbidden = set(claim["forbiddenWording"])
                self.assertFalse(forbidden & set(claim["allowedWording"]))

        self.assertIn("workflow-state.request-captured", claim_ids)
        self.assertIn("production-readiness.production-ready", claim_ids)
        self.assertEqual(
            fixture["statefulSurfaceContracts"][0]["forbiddenInference"],
            "Do not imply approval, payment, fulfillment, or production readiness from capture alone.",
        )


if __name__ == "__main__":
    unittest.main()
