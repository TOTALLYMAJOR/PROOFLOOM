from __future__ import annotations

import copy
import tempfile
import unittest
from datetime import date
from pathlib import Path

from design_intelligence.control_plane import (
    control_plane_health,
    initialize_control_plane,
    load_manifest,
    route_task_by_id,
)
from design_intelligence.planes import (
    audit_architecture_plane,
    audit_backlog,
    audit_intelligence_plane,
    audit_intent_plane,
    audit_planes,
)
from design_intelligence.storage import atomic_write_json, read_json


ROOT = Path(__file__).resolve().parents[1]


class PlaneGovernanceTests(unittest.TestCase):
    def test_repository_planes_journeys_backlog_and_routing_pass(self) -> None:
        manifest = load_manifest(ROOT)

        report = audit_planes(ROOT, manifest, today=date(2026, 8, 23))
        health = control_plane_health(ROOT)
        route = route_task_by_id(ROOT, "TASK-DESIGN-CONTROL-PLANE-PILOT")

        self.assertEqual(report["status"], "PASS", report)
        self.assertEqual(report["intent"]["journeyCoverage"]["activeJourneys"], 2)
        self.assertEqual(report["intent"]["journeyCoverage"]["orphanRequirements"], [])
        self.assertEqual(report["intent"]["backlog"]["completion"], "COMPLETE")
        self.assertFalse(report["architecture"]["certificationClaimed"])
        self.assertEqual(report["architecture"]["repositoryArchitecture"]["adrCount"], 3)
        self.assertEqual(
            report["architecture"]["repositoryArchitecture"]["technologyPolicy"],
            "contextual-not-latest",
        )
        self.assertTrue(report["intelligence"]["vendorNeutral"])
        self.assertEqual(health["status"], "PASS", health)
        self.assertEqual(route["capabilityClass"], "visual-evidence-analysis")
        self.assertFalse(route["vendorSelected"])

    def test_dry_run_discovers_repo_authorities_scripts_and_backlogs_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "docs/governance").mkdir(parents=True)
            (root / "docs/architecture").mkdir(parents=True)
            (root / "docs").mkdir(exist_ok=True)
            (root / "AGENTS.md").write_text("# Existing authority\n", encoding="utf-8")
            (root / "docs/governance/README.md").write_text("# Governance\n", encoding="utf-8")
            (root / "docs/architecture/solution.md").write_text("# Architecture\n", encoding="utf-8")
            (root / "docs/backlog-now.md").write_text("# QP-WORK-001 Current work\n", encoding="utf-8")
            (root / "package.json").write_text(
                '{"scripts":{"check:boundaries":"node check.js","prepush":"npm test"}}\n',
                encoding="utf-8",
            )
            before = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))

            report = initialize_control_plane(root, dry_run=True)

            after = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
            authority_paths = {item["path"] for item in report["discoveredAuthorities"]}
            self.assertEqual(report["status"], "REVIEW_REQUIRED")
            self.assertEqual(report["writes"], [])
            self.assertEqual(before, after)
            self.assertIn("docs/governance/README.md", authority_paths)
            self.assertIn("docs/architecture/solution.md", authority_paths)
            self.assertIn("check-boundaries", report["discoveredVerificationCommands"])
            self.assertEqual(len(report["discoveredBacklogSources"]), 2)

    def test_whole_backlog_includes_open_blocked_and_staged_items(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            atomic_write_json(root / "backlog.json", {
                "items": [
                    {"id": "WORK-001", "title": "Done", "status": "COMPLETED", "evidence": ["receipt"]},
                    {"id": "WORK-002", "title": "Ready", "status": "ACTIVE", "dependencies": ["WORK-001"]},
                    {"id": "WORK-003", "title": "Blocked", "status": "BLOCKED", "dependencies": ["WORK-002"]},
                    {"id": "WORK-004", "title": "Later", "status": "STAGED", "dependencies": []},
                ]
            })
            config = self._backlog_config("backlog.json")

            report = audit_backlog(root, config)

            self.assertEqual(report["status"], "PASS", report)
            self.assertEqual(report["completion"], "IN_PROGRESS")
            self.assertEqual(report["itemCount"], 4)
            represented = set()
            for wave in report["waves"]:
                for field in ("ready", "blocked", "staged", "waitingOnDependencies"):
                    represented.update(wave[field])
            self.assertEqual(represented, {"WORK-002", "WORK-003", "WORK-004"})

    def test_duplicate_and_unproven_terminal_backlog_items_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            atomic_write_json(root / "one.json", {
                "items": [{"id": "WORK-001", "title": "Done", "status": "COMPLETED", "evidence": []}]
            })
            atomic_write_json(root / "two.json", {
                "items": [{"id": "WORK-001", "title": "Cancelled", "status": "CANCELLED"}]
            })
            config = self._backlog_config("one.json")
            config["sources"].append({
                "path": "two.json", "role": "active", "parser": "json-items", "includeInCompletion": True
            })

            report = audit_backlog(root, config)

            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any("Duplicate backlog item" in error for error in report["errors"]))
            self.assertTrue(any("requires evidence" in error for error in report["errors"]))
            self.assertTrue(any("requires authority and rationale" in error for error in report["errors"]))

    def test_missing_dependency_and_cycle_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            atomic_write_json(root / "missing.json", {
                "items": [{
                    "id": "WORK-001",
                    "title": "Missing dependency",
                    "status": "ACTIVE",
                    "dependencies": ["WORK-404"],
                }]
            })
            missing = audit_backlog(root, self._backlog_config("missing.json"))
            atomic_write_json(root / "cycle.json", {
                "items": [
                    {"id": "WORK-001", "title": "One", "status": "ACTIVE", "dependencies": ["WORK-002"]},
                    {"id": "WORK-002", "title": "Two", "status": "ACTIVE", "dependencies": ["WORK-001"]},
                ]
            })
            cycle = audit_backlog(root, self._backlog_config("cycle.json"))

            self.assertEqual(missing["status"], "FAIL")
            self.assertTrue(any("not inventoried" in error for error in missing["errors"]))
            self.assertEqual(cycle["status"], "FAIL")
            self.assertTrue(any("dependency cycle" in error for error in cycle["errors"]))

    def test_stale_standards_profile_fails_closed(self) -> None:
        config = load_manifest(ROOT)["spec"]["planes"]["architecture"]

        report = audit_architecture_plane(ROOT, config, today=date(2026, 11, 22))

        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any("review expired" in error for error in report["errors"]))

    def test_missing_architecture_boundary_check_fails_closed(self) -> None:
        manifest = load_manifest(ROOT)
        config = copy.deepcopy(manifest["spec"]["planes"]["architecture"])
        config["boundaryChecks"].append("missing-boundary-check")

        report = audit_architecture_plane(
            ROOT,
            config,
            available_commands=set(manifest["spec"]["verification"]["commands"]),
            today=date(2026, 8, 23),
        )

        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any("not declared" in error for error in report["errors"]))

    def test_active_journey_without_test_fails_closed(self) -> None:
        temporary_index = ROOT / ".dev/intent-index.failure-test.json"
        try:
            index = copy.deepcopy(read_json(ROOT / ".dev/intent-index.json"))
            index["journeys"][0]["tests"] = []
            atomic_write_json(temporary_index, index)
            config = copy.deepcopy(load_manifest(ROOT)["spec"]["planes"]["intent"])
            config["index"] = temporary_index.relative_to(ROOT).as_posix()

            report = audit_intent_plane(ROOT, config, today=date(2026, 8, 23))

            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any("tests must not be empty" in error for error in report["errors"]))
        finally:
            temporary_index.unlink(missing_ok=True)

    def test_vendor_bound_routing_policy_fails_closed(self) -> None:
        temporary_policy = ROOT / ".dev/model-routing.failure-test.json"
        try:
            policy = copy.deepcopy(read_json(ROOT / ".dev/model-routing.json"))
            policy["capabilityClasses"][0]["capabilities"].append("openai-routing")
            atomic_write_json(temporary_policy, policy)
            config = copy.deepcopy(load_manifest(ROOT)["spec"]["planes"]["intelligence"])
            config["routingPolicy"] = temporary_policy.relative_to(ROOT).as_posix()

            report = audit_intelligence_plane(ROOT, config)

            self.assertEqual(report["status"], "FAIL")
            self.assertFalse(report["vendorNeutral"])
            self.assertTrue(any("vendor binding" in error for error in report["errors"]))
        finally:
            temporary_policy.unlink(missing_ok=True)

    @staticmethod
    def _backlog_config(path: str) -> dict:
        return {
            "completionPolicy": "all-terminal",
            "sources": [{
                "path": path,
                "role": "active",
                "parser": "json-items",
                "includeInCompletion": True,
            }],
            "terminalStatuses": ["COMPLETED", "CANCELLED", "DEFERRED_WITH_AUTHORITY"],
            "dependencies": {},
        }


if __name__ == "__main__":
    unittest.main()
