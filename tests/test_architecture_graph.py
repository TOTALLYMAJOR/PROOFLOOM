from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from design_intelligence.architecture_graph import (
    analyze_architecture_impact,
    build_architecture_graph,
)
from design_intelligence.control_plane import (
    architecture_graph_schema,
    create_task,
    initialize_control_plane,
    load_manifest,
    validate_control_plane,
)
from design_intelligence.storage import atomic_write_json


class ArchitectureGraphTests(unittest.TestCase):
    def test_graph_discovers_imports_api_schemas_journey_ownership_and_security(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            manifest = load_manifest(root)

            first = build_architecture_graph(root, manifest)
            second = build_architecture_graph(root, manifest)

            self.assertEqual(first["status"], "PASS", first)
            self.assertEqual(first["graphSha256"], second["graphSha256"])
            self.assertFalse(first["truncated"])
            self.assertFalse((root / "executed.txt").exists(), "Static discovery must not import source files")
            node_types = {node["type"] for node in first["nodes"]}
            self.assertTrue(
                {"file", "test", "package", "api", "schema", "journey", "owner", "security-boundary"}
                <= node_types
            )
            edges = {(edge["source"], edge["type"], edge["target"]) for edge in first["edges"]}
            self.assertIn(("file:src/service.py", "imports", "file:src/core.py"), edges)
            self.assertIn(("file:app/api/orders/route.ts", "exposes-api", "api:GET:/api/orders"), edges)
            self.assertIn(("file:src/client.ts", "calls-api", "api:GET:/api/orders"), edges)
            self.assertNotIn(("file:src/literal.py", "calls-api", "api:GET:/api/orders"), edges)
            self.assertIn(("file:src/schema_user.py", "uses-schema", "schema:schemas/order.schema.json"), edges)
            self.assertIn(("journey:JRN-GRAPH-001", "verified-by", "test:tests/test_feature.py"), edges)
            self.assertIn(("file:src/core.py", "owned-by", "owner:@platform"), edges)
            self.assertIn(
                ("file:src/core.py", "governed-by", "security-boundary:protected-core"),
                edges,
            )

    def test_impact_follows_downstream_blast_radius_and_protected_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            manifest = load_manifest(root)
            task = self._task()

            module_impact = analyze_architecture_impact(
                root,
                manifest,
                task,
                changed_paths=["src/core.py"],
            )
            api_impact = analyze_architecture_impact(
                root,
                manifest,
                task,
                changed_paths=["app/api/orders/route.ts"],
            )
            schema_impact = analyze_architecture_impact(
                root,
                manifest,
                task,
                changed_paths=["schemas/order.schema.json"],
            )

            self.assertEqual(module_impact["status"], "PASS", module_impact)
            self.assertTrue(
                {"src/core.py", "src/service.py", "src/consumer.py"}
                <= set(module_impact["impactedPaths"])
            )
            self.assertEqual(module_impact["requiredChecks"], ["unit-governance"])
            self.assertEqual([owner["label"] for owner in module_impact["owners"]], ["@platform"])
            self.assertTrue(module_impact["authorityRequired"])
            self.assertIn("src/client.ts", api_impact["impactedPaths"])
            self.assertIn("src/schema_user.py", schema_impact["impactedPaths"])

    def test_impact_fails_closed_when_node_budget_is_exhausted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            manifest = copy.deepcopy(load_manifest(root))
            manifest["spec"]["planes"]["architecture"]["impactGraph"]["maxImpactNodes"] = 2

            report = analyze_architecture_impact(
                root,
                manifest,
                self._task(),
                changed_paths=["src/core.py"],
            )

            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(report["truncated"])
            self.assertTrue(any("incomplete" in error for error in report["errors"]))

    def test_invalid_graph_scope_is_rejected_by_manifest_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            manifest = load_manifest(root)
            manifest["spec"]["planes"]["architecture"]["impactGraph"]["include"].append("../outside/**")
            atomic_write_json(root / "devctl.yaml", manifest)

            report = validate_control_plane(root)

            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any("repository-relative" in error for error in report["errors"]))

    def test_architecture_graph_schema_is_bundled(self) -> None:
        schema = architecture_graph_schema()

        self.assertEqual(schema["properties"]["schemaVersion"]["const"], 1)
        self.assertIn("security-boundary", schema["properties"]["nodes"]["items"]["properties"]["type"]["enum"])

    def _repository(self, root: Path) -> Path:
        (root / ".dev").mkdir(parents=True)
        (root / "src").mkdir()
        (root / "schemas").mkdir()
        (root / "tests").mkdir()
        (root / "app/api/orders").mkdir(parents=True)
        (root / ".github").mkdir()
        (root / "AGENTS.md").write_text("# Authority\n", encoding="utf-8")
        (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
        (root / "package.json").write_text(
            json.dumps({"name": "graph-fixture", "scripts": {"test": "echo test"}}),
            encoding="utf-8",
        )
        (root / "pyproject.toml").write_text(
            "[project]\nname = 'graph-fixture'\nversion = '1.0.0'\n",
            encoding="utf-8",
        )
        (root / "src/__init__.py").write_text("", encoding="utf-8")
        (root / "src/core.py").write_text(
            "from pathlib import Path\nPath('executed.txt').write_text('unsafe')\nVALUE = 1\n",
            encoding="utf-8",
        )
        (root / "src/service.py").write_text("import src.core\n", encoding="utf-8")
        (root / "src/consumer.py").write_text("import src.service\n", encoding="utf-8")
        (root / "src/schema_user.py").write_text(
            "SCHEMA = 'schemas/order.schema.json'\n",
            encoding="utf-8",
        )
        (root / "src/literal.py").write_text(
            "EXAMPLE = \"fetch('/api/orders')\"\n",
            encoding="utf-8",
        )
        (root / "src/client.ts").write_text(
            "export const load = () => fetch('/api/orders');\n",
            encoding="utf-8",
        )
        (root / "app/api/orders/route.ts").write_text(
            "export async function GET() { return Response.json([]); }\n",
            encoding="utf-8",
        )
        atomic_write_json(root / "schemas/order.schema.json", {"type": "object"})
        (root / "tests/test_feature.py").write_text("import src.consumer\n", encoding="utf-8")
        (root / ".github/CODEOWNERS").write_text("src/** @platform\n", encoding="utf-8")
        atomic_write_json(root / ".dev/intent-index.json", {
            "journeys": [{
                "id": "JRN-GRAPH-001",
                "owner": "platform owner",
                "status": "ACTIVE",
                "tests": ["tests/test_feature.py"],
            }]
        })
        initialize_control_plane(root)
        manifest = load_manifest(root)
        graph = manifest["spec"]["planes"]["architecture"]["impactGraph"]
        graph["securityRules"] = [{
            "id": "protected-core",
            "paths": ["src/core.py"],
            "classification": "protected",
            "authority": "platform owner",
            "checks": ["unit-governance"],
        }]
        graph["journeyBindings"] = [{
            "journeyId": "JRN-GRAPH-001",
            "paths": ["src/**"],
        }]
        atomic_write_json(root / "devctl.yaml", manifest)
        return root

    @staticmethod
    def _task() -> dict:
        return {
            "schemaVersion": 2,
            "id": "TASK-GRAPH",
            "title": "Graph impact",
            "status": "ACTIVE",
            "objective": "Prove bounded graph impact.",
            "nonObjectives": ["Do not execute source files."],
            "risk": "high",
            "workType": "architecture",
            "requiredCapabilities": ["dependency-analysis"],
            "intent": {
                "requirements": [],
                "journeys": ["JRN-GRAPH-001"],
                "backlogItems": ["TASK-GRAPH"],
                "successMetrics": [],
                "experiments": [],
            },
            "dependencies": [],
            "scope": {"paths": ["src/core.py"]},
            "context": {"required": ["AGENTS.md"], "optional": []},
            "verification": {"required": ["unit-governance"]},
            "completionCriteria": ["Downstream impact is bounded."],
        }


if __name__ == "__main__":
    unittest.main()
