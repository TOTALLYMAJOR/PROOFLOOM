from __future__ import annotations

import json
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from design_intelligence.operator_shell import (
    create_operator_shell_server,
    run_workflow,
    workflow_catalog,
)


ROOT = Path(__file__).resolve().parents[1]


class OperatorShellTests(unittest.TestCase):
    def test_catalog_exposes_only_governed_workflows(self) -> None:
        workflows = workflow_catalog()

        self.assertEqual(
            [workflow["id"] for workflow in workflows],
            [
                "reformat",
                "governance-audit",
                "design-audit",
                "ux-audit",
                "backlog-health",
                "build-backlog",
                "visual-qa",
            ],
        )
        self.assertEqual({workflow["actionClass"] for workflow in workflows}, {"inspect", "propose", "execute"})
        self.assertTrue(all(workflow["writes"] is False for workflow in workflows))

    def test_backlog_builder_stops_at_review_boundary(self) -> None:
        result = run_workflow(ROOT, "build-backlog", {"task": "Build the release backlog"})

        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertFalse(result["execution"]["performed"])
        self.assertFalse(result["execution"]["writes"])
        self.assertEqual(result["report"]["execution"]["authority"], "AgentFlow")

    def test_unknown_workflow_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown workflow"):
            run_workflow(ROOT, "terminal", {})

    def test_loopback_server_serves_ui_and_requires_session_token(self) -> None:
        server = create_operator_shell_server(ROOT, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            health = self._json(f"{base_url}/api/health")
            self.assertEqual(health["status"], "ok")

            bootstrap = self._json(f"{base_url}/api/bootstrap")
            self.assertEqual(bootstrap["product"], "Proofloom")
            self.assertEqual(len(bootstrap["workflows"]), 7)

            with urlopen(f"{base_url}/") as response:
                page = response.read().decode("utf-8")
                self.assertIn("Proofloom Operator Shell", page)
                self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])

            request = Request(
                f"{base_url}/api/run",
                data=json.dumps({"workflowId": "visual-qa", "inputs": {}}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(HTTPError) as denied:
                urlopen(request)
            self.assertEqual(denied.exception.code, 403)

            request.add_header("X-Proofloom-Token", bootstrap["sessionToken"])
            with urlopen(request) as response:
                result = json.load(response)
            self.assertEqual(result["status"], "READY_TO_PLAN")
            self.assertFalse(result["execution"]["performed"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    @staticmethod
    def _json(url: str) -> dict[str, object]:
        with urlopen(url) as response:
            return json.load(response)


if __name__ == "__main__":
    unittest.main()
