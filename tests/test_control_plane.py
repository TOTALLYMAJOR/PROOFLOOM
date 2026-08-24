from __future__ import annotations

import contextlib
import io
import json
import tempfile
import tomllib
import unittest
from pathlib import Path

from design_intelligence import __version__
from design_intelligence.control_plane import (
    analyze_impact,
    architecture_graph,
    audit_design_adoption,
    audit_visual_evidence,
    create_task,
    initialize_control_plane,
    load_manifest,
    manifest_schema,
    run_control_plane_doctor,
    task_context,
    task_packet_schema,
    validate_control_plane,
)
from design_intelligence.devctl_cli import main as devctl_main
from design_intelligence.storage import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]


class ControlPlaneTests(unittest.TestCase):
    def test_release_versions_are_aligned(self) -> None:
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        package_lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        versions = {
            (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
            package["version"],
            package_lock["version"],
            package_lock["packages"][""]["version"],
            project["project"]["version"],
            __version__,
        }

        self.assertEqual(versions, {"5.0.1"})

    def test_repository_manifest_and_bundled_schemas_validate(self) -> None:
        report = validate_control_plane(ROOT)

        self.assertEqual(report["status"], "PASS", report)
        self.assertEqual(manifest_schema()["properties"]["apiVersion"]["const"], "devctl.design-intelligence/v2")
        self.assertEqual(task_packet_schema()["properties"]["schemaVersion"]["const"], 2)

    def test_init_is_additive_idempotent_and_does_not_create_design_authorities(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "AGENTS.md").write_text("# Existing authority\n", encoding="utf-8")
            (root / "README.md").write_text("# Product\n", encoding="utf-8")

            first = initialize_control_plane(root)
            second = initialize_control_plane(root)

            self.assertEqual(first["status"], "INITIALIZED")
            self.assertEqual(second["status"], "ALREADY_CONFIGURED")
            self.assertFalse((root / ".design").exists())
            self.assertEqual((root / "AGENTS.md").read_text(encoding="utf-8"), "# Existing authority\n")
            self.assertEqual(second["writes"], [])

    def test_validation_fails_when_declared_authority_disappears(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            authority = root / "AGENTS.md"
            authority.write_text("# Authority\n", encoding="utf-8")
            initialize_control_plane(root)
            authority.unlink()

            report = validate_control_plane(root)

            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any("does not exist" in error for error in report["errors"]))

    def test_task_context_is_trust_ranked_bounded_and_denies_secret_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._initialized_repo(Path(temporary))
            (root / "src").mkdir()
            (root / "src/app.py").write_text("print('bounded')\n", encoding="utf-8")
            (root / ".env.production").write_text("TOKEN=never-read\n", encoding="utf-8")
            created = create_task(root, self._task())

            report = task_context(root, created["taskId"], max_files=4)

            self.assertEqual(report["status"], "PASS", report)
            self.assertLessEqual(report["selectedFiles"], 4)
            self.assertEqual(report["records"][0]["trust"], "repository-governance")
            self.assertNotIn(".env.production", [record["path"] for record in report["records"]])

            denied = self._task(identifier="TASK-DENIED")
            denied["context"]["required"] = [".env.production"]
            create_task(root, denied)
            denied_report = task_context(root, "TASK-DENIED")
            self.assertEqual(denied_report["status"], "FAIL")
            self.assertTrue(any("neverAutoLoad" in error for error in denied_report["errors"]))

    def test_task_creation_rejects_path_escape_and_unknown_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._initialized_repo(Path(temporary))
            packet = self._task()
            packet["scope"]["paths"] = ["../outside"]
            packet["verification"]["required"] = ["unknown-check"]

            with self.assertRaisesRegex(ValueError, "repository-relative"):
                create_task(root, packet)

    def test_impact_selects_affected_checks_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "AGENTS.md").write_text("# Authority\n", encoding="utf-8")
            (root / "package.json").write_text(
                json.dumps({"scripts": {"design:ci:standard": "echo visual"}}),
                encoding="utf-8",
            )
            (root / "tests").mkdir()
            (root / "tests/test_example.py").write_text("pass\n", encoding="utf-8")
            (root / "pyproject.toml").write_text("[project]\nname = 'fixture'\n", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src/App.tsx").write_text("export default function App() {}\n", encoding="utf-8")
            initialize_control_plane(root)
            packet = self._task()
            packet["verification"]["required"] = ["unit-governance"]
            create_task(root, packet)

            report = analyze_impact(root, packet["id"], changed_paths=["src/App.tsx"])

            self.assertEqual(report["status"], "PASS", report)
            self.assertEqual({item["id"] for item in report["checks"]}, {"design-standard", "unit-governance"})
            self.assertFalse(report["execution"]["performed"])

    def test_existing_design_and_visual_evidence_are_delegated_and_audited(self) -> None:
        adoption = audit_design_adoption(
            ROOT,
            "artifacts/design/adoptions/preserve-evidence-first-design-qa-hierarchy-v11/adoption-report.json",
        )
        visual = audit_visual_evidence(
            ROOT,
            "artifacts/design/reports/design-department-surface/qa-report.json",
        )

        self.assertEqual(adoption["status"], "PASS", adoption)
        self.assertFalse(adoption["duplicatedInfrastructure"])
        self.assertEqual(visual["status"], "PASS", visual)
        self.assertEqual(visual["quality"]["score"], 100)
        self.assertFalse(visual["duplicatedInfrastructure"])

    def test_visual_audit_fails_closed_for_incomplete_qa_evidence(self) -> None:
        incomplete = ROOT / "artifacts/control-plane/incomplete-qa-report.test.json"
        try:
            atomic_write_json(incomplete, {"viewports": [], "totals": {}, "repairIterations": 0})
            report = audit_visual_evidence(ROOT, incomplete)
            self.assertEqual(report["status"], "FAIL")
            self.assertIn("Deterministic quality score did not pass", report["errors"])
        finally:
            incomplete.unlink(missing_ok=True)

    def test_doctor_and_cli_smoke(self) -> None:
        doctor = run_control_plane_doctor(ROOT)
        graph = architecture_graph(ROOT)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = devctl_main(["validate", "--root", str(ROOT), "--format", "json"])

        self.assertEqual(doctor["status"], "PASS", doctor)
        self.assertEqual(graph["status"], "PASS", graph)
        self.assertFalse(graph["truncated"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "PASS")

        graph_output = io.StringIO()
        with contextlib.redirect_stdout(graph_output):
            graph_exit = devctl_main([
                "architecture", "graph", "--summary", "--root", str(ROOT), "--format", "json"
            ])
        graph_summary = json.loads(graph_output.getvalue())
        self.assertEqual(graph_exit, 0)
        self.assertEqual(graph_summary["status"], "PASS")
        self.assertNotIn("nodes", graph_summary)
        self.assertNotIn("edges", graph_summary)

    def _initialized_repo(self, root: Path) -> Path:
        (root / "AGENTS.md").write_text("# Authority\n", encoding="utf-8")
        (root / "README.md").write_text("# Product\n", encoding="utf-8")
        (root / "tests").mkdir()
        (root / "tests/test_fixture.py").write_text("# fixture\n", encoding="utf-8")
        (root / "pyproject.toml").write_text("[project]\nname = 'fixture'\n", encoding="utf-8")
        initialize_control_plane(root)
        return root

    def _task(self, identifier: str = "TASK-BOUNDED") -> dict:
        return {
            "schemaVersion": 2,
            "id": identifier,
            "title": "Bounded task",
            "status": "ACTIVE",
            "objective": "Prove bounded context and affected verification.",
            "nonObjectives": ["Do not mutate unrelated files."],
            "risk": "medium",
            "workType": "maintenance",
            "requiredCapabilities": ["repository-analysis", "structured-output"],
            "intent": {
                "requirements": [],
                "journeys": [],
                "backlogItems": [identifier],
                "successMetrics": [],
                "experiments": [],
            },
            "dependencies": [],
            "scope": {"paths": ["src/**"]},
            "context": {"required": ["AGENTS.md"], "optional": ["README.md"]},
            "verification": {"required": ["unit-governance"]},
            "completionCriteria": ["Affected checks are selected deterministically."],
        }


if __name__ == "__main__":
    unittest.main()
