from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from design_intelligence.architecture_graph import build_architecture_graph
from design_intelligence.storage import atomic_write_json


class RepositoryFinalizationGraphTests(unittest.TestCase):
    def test_graph_does_not_discover_packages_inside_excluded_trees(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app").mkdir()
            (root / "app/page.tsx").write_text("export default function Page() { return null; }\n", encoding="utf-8")
            atomic_write_json(root / "package.json", {"name": "root-package"})
            excluded = root / "node_modules/excluded-package"
            excluded.mkdir(parents=True)
            atomic_write_json(excluded / "package.json", {"name": "must-not-be-discovered"})

            report = build_architecture_graph(root, self._manifest())

            self.assertEqual(report["status"], "PASS", report)
            self.assertNotIn("must-not-be-discovered", {node["label"] for node in report["nodes"]})

    def test_exact_next_dynamic_route_binding_is_not_treated_as_a_glob(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            route = root / "app/api/orders/[token]/route.ts"
            route.parent.mkdir(parents=True)
            route.write_text("export async function GET() { return Response.json({}); }\n", encoding="utf-8")
            (root / ".dev").mkdir()
            atomic_write_json(root / ".dev/intent-index.json", {
                "journeys": [{"id": "JRN-GRAPH-001", "status": "ACTIVE", "tests": []}],
            })
            manifest = self._manifest()
            manifest["spec"]["planes"]["intent"] = {
                "enabled": True,
                "index": ".dev/intent-index.json",
            }
            manifest["spec"]["planes"]["architecture"]["impactGraph"]["journeyBindings"] = [{
                "journeyId": "JRN-GRAPH-001",
                "paths": ["app/api/orders/[token]/route.ts"],
            }]

            report = build_architecture_graph(root, manifest)

            self.assertEqual(report["status"], "PASS", report)
            self.assertIn(
                ("journey:JRN-GRAPH-001", "implemented-by", "file:app/api/orders/[token]/route.ts"),
                {(edge["source"], edge["type"], edge["target"]) for edge in report["edges"]},
            )

    @staticmethod
    def _manifest() -> dict:
        return {
            "spec": {
                "planes": {
                    "architecture": {
                        "impactGraph": {
                            "enabled": True,
                            "include": ["app/**", "*.json"],
                            "exclude": ["node_modules/**", ".git/**"],
                            "maxSourceFiles": 50,
                            "maxNodes": 100,
                            "maxImpactNodes": 50,
                            "maxDepth": 3,
                            "codeowners": [],
                            "ownershipRules": [],
                            "securityRules": [],
                            "journeyBindings": [],
                        }
                    }
                }
            }
        }


if __name__ == "__main__":
    unittest.main()
