from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from design_intelligence.baselines import (
    audit_baseline_review_request,
    create_baseline_review_request,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class GovernanceV3Tests(unittest.TestCase):
    def test_reviewable_request_binds_evidence_without_mutating_baselines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qa_path, model_path, candidate_root = self._write_evidence(root)
            output = root / "artifacts/design/baseline-requests/surface.json"

            request = create_baseline_review_request(
                root,
                "surface",
                "Test Product",
                qa_path,
                model_path,
                candidate_root,
                "agent:test",
                output,
            )

            self.assertEqual(request["status"], "REVIEWABLE")
            self.assertFalse(request["baselineMutationPerformed"])
            self.assertEqual(request["promotionAuthority"], "human-required")
            self.assertEqual(len(request["candidates"]), 5)
            self.assertFalse((root / ".design/baselines").exists())
            self.assertEqual(audit_baseline_review_request(root, output)["status"], "PASS")

            first_candidate = next(iter(request["candidates"].values()))
            (root / first_candidate["path"]).write_bytes(b"changed")
            audit = audit_baseline_review_request(root, output)
            self.assertEqual(audit["status"], "FAIL")
            self.assertTrue(any("hash mismatch" in error for error in audit["errors"]))

    def test_failed_qa_and_model_review_create_blocked_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qa_path, model_path, candidate_root = self._write_evidence(
                root,
                qa_status="FAIL",
                serious_violations=6,
                model_verdict="FAIL",
                model_severity="P1",
            )
            output = root / "artifacts/design/baseline-requests/surface.json"

            request = create_baseline_review_request(
                root,
                "surface",
                "Test Product",
                qa_path,
                model_path,
                candidate_root,
                "agent:test",
                output,
            )

            self.assertEqual(request["status"], "BLOCKED")
            self.assertTrue(any("serious accessibility" in blocker for blocker in request["blockers"]))
            self.assertTrue(any("model visual review failed" in blocker for blocker in request["blockers"]))
            self.assertEqual(audit_baseline_review_request(root, output)["status"], "PASS")
            self.assertFalse((root / ".design/baselines").exists())

            request["status"] = "REVIEWABLE"
            request["blockers"] = []
            output.write_text(json.dumps(request), encoding="utf-8")
            tampered = audit_baseline_review_request(root, output)
            self.assertEqual(tampered["status"], "FAIL")
            self.assertTrue(any("bound evidence" in error for error in tampered["errors"]))

    def test_remote_ci_is_read_only_and_tiered(self) -> None:
        workflow = (REPOSITORY_ROOT / ".github/workflows/design-ci.yml").read_text(encoding="utf-8")

        self.assertIn("pull_request:", workflow)
        self.assertIn("quick:", workflow)
        self.assertIn("standard:", workflow)
        self.assertIn("full:", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("actions/checkout@v7", workflow)
        self.assertIn("actions/setup-python@v7", workflow)
        self.assertIn("actions/setup-node@v7", workflow)
        self.assertIn("actions/upload-artifact@v7", workflow)
        self.assertNotIn("pull_request_target", workflow)
        self.assertNotIn("baseline promote", workflow)
        self.assertNotIn("repair --apply", workflow)

    def _write_evidence(
        self,
        root: Path,
        *,
        qa_status: str = "PASS",
        serious_violations: int = 0,
        model_verdict: str = "WARN",
        model_severity: str = "P2",
    ) -> tuple[Path, Path, Path]:
        thresholds = root / ".design/quality/thresholds.json"
        thresholds.parent.mkdir(parents=True)
        thresholds.write_text(json.dumps({"requiredViewportCount": 5}), encoding="utf-8")
        candidate_root = root / "artifacts/design/screenshots/surface"
        viewports = []
        for index in range(5):
            viewport_id = f"viewport-{index + 1}"
            screenshot = candidate_root / viewport_id / "current.png"
            screenshot.parent.mkdir(parents=True)
            screenshot.write_bytes(f"png-{index}".encode())
            viewports.append({
                "id": viewport_id,
                "status": "PASS" if qa_status == "PASS" else ("FAIL" if index == 0 else "PASS"),
                "artifacts": {"currentScreenshot": screenshot.relative_to(root).as_posix()},
            })
        qa = {
            "surface": "Test surface",
            "status": qa_status,
            "sourceRevision": {
                "repository": "test",
                "branch": "test",
                "commitSha": "abcdef1234567890",
            },
            "viewports": viewports,
            "totals": {
                "criticalAccessibilityViolations": 0,
                "seriousAccessibilityViolations": serious_violations,
                "containmentFailures": 0,
                "domAssertionsPassed": 25,
                "domAssertionsTotal": 25,
                "contractAssertionsPassed": 25,
                "contractAssertionsTotal": 25,
            },
        }
        model = {
            "surface": "Test surface",
            "verdict": model_verdict,
            "severity": model_severity,
        }
        qa_path = root / "artifacts/design/reports/surface/qa-report.json"
        model_path = root / "artifacts/design/reports/surface/model-visual-review.json"
        qa_path.parent.mkdir(parents=True)
        qa_path.write_text(json.dumps(qa), encoding="utf-8")
        model_path.write_text(json.dumps(model), encoding="utf-8")
        return qa_path, model_path, candidate_root


if __name__ == "__main__":
    unittest.main()
