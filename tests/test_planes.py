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
    DEFAULT_BACKLOG_DRAFTING_POLICY,
    audit_architecture_plane,
    audit_backlog,
    audit_intelligence_plane,
    audit_intent_plane,
    audit_planes,
)
from design_intelligence.storage import atomic_write_json, read_json


ROOT = Path(__file__).resolve().parents[1]


class PlaneGovernanceTests(unittest.TestCase):
    def test_repository_planes_journeys_backlog_and_routing_are_consistent(self) -> None:
        manifest = load_manifest(ROOT)

        report = audit_planes(ROOT, manifest, today=date(2026, 8, 23))
        health = control_plane_health(ROOT)
        route = route_task_by_id(ROOT, "TASK-DESIGN-CONTROL-PLANE-PILOT")
        backlog = report["intent"]["backlog"]

        self.assertEqual(report["status"], "PASS", report)
        self.assertGreaterEqual(report["intent"]["journeyCoverage"]["activeJourneys"], 2)
        self.assertEqual(report["intent"]["journeyCoverage"]["orphanRequirements"], [])
        self.assertEqual(backlog["itemCount"], backlog["openCount"] + backlog["terminalCount"])
        self.assertEqual(
            backlog["completion"],
            "COMPLETE" if backlog["openCount"] == 0 else "IN_PROGRESS",
        )
        self.assertFalse(report["architecture"]["certificationClaimed"])
        self.assertGreaterEqual(report["architecture"]["repositoryArchitecture"]["adrCount"], 3)
        self.assertEqual(
            report["architecture"]["repositoryArchitecture"]["technologyPolicy"],
            "contextual-not-latest",
        )
        self.assertTrue(report["intelligence"]["vendorNeutral"])
        self.assertEqual(health["status"], "WARN", health)
        self.assertEqual(health["backlog"]["completion"], "IN_PROGRESS")
        self.assertGreater(health["backlog"]["open"], 0)
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
            self.assertEqual(
                [item["path"] for item in report["discoveredBacklogSources"]],
                ["docs/backlog-now.md"],
            )

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

    def test_markdown_source_precedence_ignores_pointer_duplicates_not_real_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "backlog-now.md").write_text(
                "### WORK-001: Active item\nStatus: active\n#### WORK-001 Delivery Map\n",
                encoding="utf-8",
            )
            (root / "backlog-next.md").write_text(
                "### WORK-001: Active pointer\nStatus: active\n### WORK-002: Staged item\nStatus: planned\n",
                encoding="utf-8",
            )
            config = {
                "completionPolicy": "all-terminal",
                "sources": [
                    {
                        "path": "backlog-now.md",
                        "role": "active",
                        "parser": "markdown-headings",
                        "includeInCompletion": True,
                        "headingLevels": [3],
                    },
                    {
                        "path": "backlog-next.md",
                        "role": "staged",
                        "parser": "markdown-headings",
                        "includeInCompletion": True,
                        "headingLevels": [3],
                        "shadowedBy": "backlog-now.md",
                    },
                ],
                "terminalStatuses": ["COMPLETED", "CANCELLED", "DEFERRED_WITH_AUTHORITY"],
                "dependencies": {},
            }

            report = audit_backlog(root, config)

            self.assertEqual(report["status"], "PASS", report)
            self.assertEqual(report["itemCount"], 2)
            self.assertEqual([item["id"] for item in report["items"]], ["WORK-001", "WORK-002"])
            self.assertEqual(report["shadowedRecords"], [
                {
                    "id": "WORK-001",
                    "source": "backlog-next.md",
                    "shadowedBy": "backlog-now.md",
                }
            ])

    def test_markdown_recently_closed_items_require_and_preserve_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "evidence.md").write_text("# Proof\n", encoding="utf-8")
            (root / "backlog.md").write_text(
                "#### Recently Closed\n"
                "### WORK-001: Verified work\n"
                "- Closed in current source by `evidence.md`.\n",
                encoding="utf-8",
            )
            config = self._backlog_config("backlog.md")
            config["sources"][0].update({
                "parser": "markdown-headings",
                "headingLevels": [3],
            })

            report = audit_backlog(root, config)

            self.assertEqual(report["status"], "PASS", report)
            self.assertEqual(report["completion"], "COMPLETE")
            self.assertEqual(report["items"][0]["status"], "COMPLETED")
            self.assertEqual(report["items"][0]["evidence"], ["evidence.md"])

    def test_manifest_dependencies_augment_markdown_backlog_items(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "backlog.md").write_text(
                "### WORK-001: Foundation\nStatus: active\n"
                "### WORK-002: Dependent work\nStatus: active\n",
                encoding="utf-8",
            )
            config = self._backlog_config("backlog.md")
            config["sources"][0].update({
                "parser": "markdown-headings",
                "headingLevels": [3],
            })
            config["dependencies"] = {"WORK-002": ["WORK-001"]}

            report = audit_backlog(root, config)

            self.assertEqual(report["status"], "PASS", report)
            records = {item["id"]: item for item in report["items"]}
            self.assertEqual(records["WORK-002"]["dependencies"], ["WORK-001"])
            self.assertEqual(report["waves"][0]["ready"], ["WORK-001"])
            self.assertEqual(report["waves"][1]["ready"], ["WORK-002"])

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

    def test_task_store_enforces_drafting_acceptance_and_dependency_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            active = root / ".dev/tasks/active"
            active.mkdir(parents=True)
            dependency = self._task_packet("TASK-DEPENDENCY", status="STAGED")
            consumer = self._task_packet(
                "TASK-CONSUMER",
                status="ACTIVE",
                dependencies=["TASK-DEPENDENCY"],
            )
            atomic_write_json(active / "TASK-DEPENDENCY.json", dependency)
            atomic_write_json(active / "TASK-CONSUMER.json", consumer)
            config = {
                "completionPolicy": "all-terminal",
                "draftingPolicy": dict(DEFAULT_BACKLOG_DRAFTING_POLICY),
                "sources": [{
                    "path": ".dev/tasks",
                    "role": "active",
                    "parser": "task-store",
                    "includeInCompletion": True,
                }],
                "terminalStatuses": ["COMPLETED", "CANCELLED", "DEFERRED_WITH_AUTHORITY"],
                "dependencies": {},
            }

            report = audit_backlog(root, config)
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any("not completed" in error for error in report["errors"]))

            consumer["status"] = "STAGED"
            consumer.pop("acceptance")
            atomic_write_json(active / "TASK-CONSUMER.json", consumer)
            report = audit_backlog(root, config)
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any("task.acceptance" in error for error in report["errors"]))

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

    @staticmethod
    def _task_packet(
        identifier: str,
        *,
        status: str,
        dependencies: list[str] | None = None,
    ) -> dict:
        return {
            "schemaVersion": 3,
            "id": identifier,
            "title": identifier,
            "status": status,
            "risk": "high",
            "completionCriteria": ["The governed behavior is demonstrated."],
            "dependencies": dependencies or [],
            "authorityBoundaries": ["repositoryMutation"],
            "verification": {"required": ["unit-governance"]},
            "acceptance": {
                "evidenceRequired": ["Focused tests pass."],
                "humanDecision": "REQUIRED",
                "decisionAuthority": "repository owner",
                "claimBoundary": "Acceptance proves local behavior only.",
            },
        }


if __name__ == "__main__":
    unittest.main()
