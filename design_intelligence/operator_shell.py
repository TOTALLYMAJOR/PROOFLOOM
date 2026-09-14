from __future__ import annotations

import json
import secrets
import subprocess
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import __version__
from .backlog_assembly import (
    DEFAULT_OUTPUT_PATH,
    assemble_backlog_brief,
    save_backlog_proposal,
    validate_backlog_proposal,
)
from .context import build_context
from .control_plane import load_manifest, program_status
from .governance import audit_governance, governance_design_preflight
from .planes import audit_backlog
from .validation import validate_repository
from .workflows import build_start_packet, build_workflow


WORKFLOWS: tuple[dict[str, Any], ...] = (
    {
        "id": "reformat",
        "label": "Reformat surface",
        "eyebrow": "Design proposal",
        "description": "Shape a bounded visual, hierarchy, responsive, workflow, or component-conformity mission.",
        "actionClass": "propose",
        "buttonLabel": "Generate directions",
        "requiresTask": True,
        "writes": False,
        "authority": "Human direction selection",
        "proofBoundary": "A direction proposal does not authorize implementation.",
    },
    {
        "id": "governance-audit",
        "label": "Governance audit",
        "eyebrow": "Repository truth",
        "description": "Map governing sources, conflicts, drift, damaged controls, and readiness before design.",
        "actionClass": "inspect",
        "buttonLabel": "Run governance audit",
        "requiresTask": False,
        "writes": False,
        "authority": "Repository governance",
        "proofBoundary": "Audit findings describe repository evidence; they do not approve authority changes.",
    },
    {
        "id": "design-audit",
        "label": "Design audit",
        "eyebrow": "Deterministic review",
        "description": "Inspect repository fit and design drift without replacing the existing design system.",
        "actionClass": "inspect",
        "buttonLabel": "Run design audit",
        "requiresTask": False,
        "writes": False,
        "authority": "Existing design system",
        "proofBoundary": "Without a visual-review manifest, the result covers repository fit and deterministic linting only.",
    },
    {
        "id": "ux-audit",
        "label": "UX audit",
        "eyebrow": "Journey clarity",
        "description": "Build an actor-task model and expose workflow, state, blocker, and recovery requirements.",
        "actionClass": "inspect",
        "buttonLabel": "Run UX audit",
        "requiresTask": True,
        "writes": False,
        "authority": "Product and journey truth",
        "proofBoundary": "The audit proposes coverage; it does not prove runtime reachability or create tests.",
    },
    {
        "id": "backlog-health",
        "label": "Backlog health",
        "eyebrow": "Whole portfolio",
        "description": "Check declared backlog sources, dependencies, execution waves, and terminal evidence.",
        "actionClass": "inspect",
        "buttonLabel": "Inspect backlog",
        "requiresTask": False,
        "writes": False,
        "authority": "Declared backlog sources",
        "proofBoundary": "Backlog status cannot mark work complete without its required terminal evidence.",
    },
    {
        "id": "build-backlog",
        "label": "Build proposed backlog",
        "eyebrow": "Governed AI assembly",
        "description": "Give an AI a repository-bound brief, validate its dependency-aware draft, and explicitly save a non-canonical proposal.",
        "actionClass": "propose",
        "buttonLabel": "Assemble AI brief",
        "requiresTask": True,
        "writes": False,
        "authority": "Repository truth, then human review",
        "proofBoundary": "A saved proposal is not the canonical backlog and does not authorize AgentFlow execution.",
    },
    {
        "id": "visual-qa",
        "label": "Visual QA",
        "eyebrow": "Rendered proof",
        "description": "Prepare the governed browser, viewport, accessibility, and baseline evidence lane.",
        "actionClass": "execute",
        "buttonLabel": "Review QA plan",
        "requiresTask": False,
        "writes": False,
        "authority": "Existing Playwright hierarchy",
        "proofBoundary": "This shell returns the plan only; a separate explicit QA run creates local evidence.",
    },
)

WORKFLOW_BY_ID = {item["id"]: item for item in WORKFLOWS}
MAX_REQUEST_BYTES = 512 * 1024
STATIC_ROOT = files("design_intelligence").joinpath("operator_shell_static")
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/proofloom-mark.svg": ("proofloom-mark.svg", "image/svg+xml"),
}


def workflow_catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in WORKFLOWS]


def repository_summary(repository_root: str | Path) -> dict[str, Any]:
    root = _repository_root(repository_root)
    status_output = _git(root, "status", "--porcelain")
    preflight = governance_design_preflight(root)
    return {
        "root": str(root),
        "name": root.name,
        "branch": _git(root, "branch", "--show-current") or "detached",
        "commit": _git(root, "rev-parse", "HEAD") or "unavailable",
        "dirty": bool(status_output),
        "changedPaths": len(status_output.splitlines()) if status_output else 0,
        "governanceGate": preflight.get("status", "UNKNOWN"),
        "gateReason": preflight.get("designGate", {}).get("reason")
        or preflight.get("reason")
        or "No governance explanation was returned.",
    }


def bootstrap_payload(repository_root: str | Path) -> dict[str, Any]:
    return {
        "product": "Proofloom",
        "service": "Design Intelligence Operator Shell",
        "version": __version__,
        "repository": repository_summary(repository_root),
        "workflows": workflow_catalog(),
        "executionBoundary": (
            "Read-only inspection runs locally. Proposals require review. Implementation remains AgentFlow-owned."
        ),
    }


def run_workflow(
    repository_root: str | Path,
    workflow_id: str,
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = _repository_root(repository_root)
    workflow = WORKFLOW_BY_ID.get(workflow_id)
    if workflow is None:
        raise ValueError(f"Unknown workflow: {workflow_id}")
    values = inputs if isinstance(inputs, dict) else {}
    task = _clean_text(values.get("task"), maximum=500)
    surface = _clean_text(values.get("surface"), maximum=200) or None
    profile = _clean_text(values.get("profile"), maximum=40) or None
    if profile not in {None, "quotepilot", "quietpilot", "leaguepilot"}:
        raise ValueError("profile must be quotepilot, quietpilot, or leaguepilot")
    if workflow["requiresTask"] and not task:
        raise ValueError("This workflow requires a task or focus statement.")

    if workflow_id == "governance-audit":
        report = audit_governance(root)
        next_action = "Review blocking findings before changing repository authority."
    elif workflow_id == "design-audit":
        report = validate_repository(str(root)).to_dict()
        next_action = "Classify findings before changing the interface or design system."
    elif workflow_id == "ux-audit":
        context = build_context(str(root), profile, {"goal": task})
        planned = build_workflow(str(root), task, profile, surface)
        report = {
            "status": planned["status"],
            "actorTaskModel": context.actor_task_model.to_dict(),
            "designLanguageFocus": context.design_language_focus,
            "validationFocus": context.validation_focus,
            "contract": planned["contract"],
            "workflow": planned["workflow"],
        }
        next_action = "Review the actor, state, blocker, authority, and recovery coverage."
    elif workflow_id == "backlog-health":
        manifest = load_manifest(root)
        config = manifest["spec"]["planes"]["intent"]["backlog"]
        report = audit_backlog(root, config)
        next_action = "Review the next dependency-safe wave and any non-terminal evidence gaps."
    elif workflow_id == "reformat":
        preflight = governance_design_preflight(root)
        if preflight.get("status") != "PASS":
            report = {
                "status": "GOVERNANCE_REQUIRED",
                "implementationReady": False,
                "governancePreflight": preflight,
            }
        else:
            packet = build_start_packet(
                str(root),
                task,
                profile_name=profile,
                surface=surface,
            )
            report = {
                "status": packet["status"],
                "implementationReady": packet["mission"]["implementationReady"],
                "recommendedDirection": packet["mission"]["recommendedDirection"],
                "selectedDirection": packet["mission"]["selectedDirection"],
                "directions": packet["mission"]["directions"],
                "proofGate": packet["mission"]["proofGate"],
                "contractPreview": packet["workflow"]["contract"],
            }
        next_action = "Select and approve a direction before requesting implementation."
    elif workflow_id == "build-backlog":
        phase = _clean_text(values.get("phase"), maximum=20) or "assemble"
        if phase == "assemble":
            brief = assemble_backlog_brief(root, task, surface=surface)
            report = {
                "status": brief["status"],
                "phase": phase,
                "brief": brief,
                "currentProgram": _program_status_or_governance(root),
                "execution": {"performed": False, "authority": "AgentFlow"},
            }
            next_action = brief["nextAction"]
        elif phase == "validate":
            validation = validate_backlog_proposal(
                root,
                values.get("proposal", ""),
                expected_objective=task,
            )
            report = {
                "status": validation["status"],
                "phase": phase,
                "validation": validation,
                "execution": {"performed": False, "authority": "AgentFlow"},
            }
            next_action = (
                "Resolve every validation finding, or confirm the output path and explicitly save the reviewed proposal."
                if validation["status"] == "VALID"
                else "Return the validation findings to the AI, then validate the corrected JSON draft."
            )
        elif phase == "save":
            if values.get("confirmSave") is not True:
                raise ValueError("Explicit save confirmation is required")
            saved = save_backlog_proposal(
                root,
                values.get("proposal", ""),
                _clean_text(values.get("outputPath"), maximum=500) or DEFAULT_OUTPUT_PATH,
                expected_objective=task,
            )
            report = {
                "status": saved["status"],
                "phase": phase,
                "savedProposal": saved,
                "execution": {"performed": False, "authority": "AgentFlow"},
            }
            next_action = saved["nextAction"]
        else:
            raise ValueError("build-backlog phase must be assemble, validate, or save")
    else:
        report = {
            "status": "READY_TO_PLAN",
            "scenario": "tests/design/scenarios/operator-shell.json",
            "viewports": [1440, 1280, 1024, 768, 390],
            "browsers": ["chromium", "firefox", "webkit"],
            "checks": [
                "workflow hierarchy",
                "keyboard and accessible names",
                "horizontal containment",
                "off-screen controls",
                "browser-scoped evidence",
            ],
            "command": "npm run design:qa:operator-shell",
            "execution": {"performed": False, "authority": "Explicit operator action"},
        }
        next_action = "Start the shell on port 8787, then run the declared operator-shell QA command."

    write_performed = workflow_id == "build-backlog" and report.get("phase") == "save"
    return {
        "runId": f"run-{secrets.token_hex(6)}",
        "observedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "workflow": dict(workflow),
        "status": report.get("status", "UNKNOWN"),
        "nextAction": next_action,
        "execution": {
            "performed": False,
            "authority": workflow["authority"],
            "writes": write_performed,
        },
        "proofBoundary": workflow["proofBoundary"],
        "report": report,
    }


class OperatorShellServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], repository_root: Path):
        self.repository_root = repository_root
        self.session_token = secrets.token_urlsafe(32)
        super().__init__(address, OperatorShellHandler)


class OperatorShellHandler(BaseHTTPRequestHandler):
    server: OperatorShellServer

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = urlparse(self.path).path
        if not self._host_allowed():
            self._json(HTTPStatus.FORBIDDEN, {"status": "FORBIDDEN", "error": "Loopback host required."})
            return
        if path == "/api/health":
            self._json(HTTPStatus.OK, {"status": "ok", "service": "proofloom-operator-shell"})
            return
        if path == "/api/bootstrap":
            payload = bootstrap_payload(self.server.repository_root)
            payload["sessionToken"] = self.server.session_token
            self._json(HTTPStatus.OK, payload)
            return
        static = STATIC_FILES.get(path)
        if static is None:
            self._json(HTTPStatus.NOT_FOUND, {"status": "NOT_FOUND"})
            return
        name, content_type = static
        try:
            content = STATIC_ROOT.joinpath(name).read_bytes()
        except FileNotFoundError:
            self._json(HTTPStatus.NOT_FOUND, {"status": "NOT_FOUND"})
            return
        self._bytes(HTTPStatus.OK, content, content_type)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = urlparse(self.path).path
        if not self._host_allowed():
            self._json(HTTPStatus.FORBIDDEN, {"status": "FORBIDDEN", "error": "Loopback host required."})
            return
        if path != "/api/run":
            self._json(HTTPStatus.NOT_FOUND, {"status": "NOT_FOUND"})
            return
        if self.headers.get("X-Proofloom-Token") != self.server.session_token:
            self._json(HTTPStatus.FORBIDDEN, {"status": "FORBIDDEN", "error": "Invalid shell session."})
            return
        try:
            body = self._request_json()
            result = run_workflow(
                self.server.repository_root,
                str(body.get("workflowId", "")),
                body.get("inputs"),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"status": "INVALID_REQUEST", "error": str(error)})
            return
        except Exception as error:  # pragma: no cover - defensive API boundary
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"status": "ERROR", "error": str(error)})
            return
        self._json(HTTPStatus.OK, result)

    def _request_json(self) -> dict[str, Any]:
        if self.headers.get_content_type() != "application/json":
            raise ValueError("Content-Type must be application/json")
        raw_length = self.headers.get("Content-Length", "0")
        length = int(raw_length)
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("Request body must be between 1 byte and 512 KiB")
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise ValueError("Request body must be a JSON object")
        return value

    def _host_allowed(self) -> bool:
        host = self.headers.get("Host", "")
        name = host.rsplit(":", 1)[0].strip("[]").lower()
        return name in {"127.0.0.1", "localhost"}

    def _json(self, status: HTTPStatus, value: dict[str, Any]) -> None:
        self._bytes(status, (json.dumps(value, indent=2) + "\n").encode("utf-8"), "application/json; charset=utf-8")

    def _bytes(self, status: HTTPStatus, value: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(value)))
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'self'",
        )
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(value)

    def log_message(self, format: str, *args: Any) -> None:
        return


def create_operator_shell_server(
    repository_root: str | Path,
    host: str = "127.0.0.1",
    port: int = 8787,
) -> OperatorShellServer:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("The operator shell is loopback-only; host must be 127.0.0.1 or localhost")
    if not 0 <= port <= 65535:
        raise ValueError("port must be between 0 and 65535")
    return OperatorShellServer((host, port), _repository_root(repository_root))


def serve_operator_shell(
    repository_root: str | Path,
    host: str = "127.0.0.1",
    port: int = 8787,
    open_browser: bool = False,
) -> int:
    server = create_operator_shell_server(repository_root, host, port)
    actual_port = server.server_address[1]
    url = f"http://{host}:{actual_port}/"
    print(f"Proofloom Operator Shell: {url}", flush=True)
    print(f"Bound repository: {server.repository_root}", flush=True)
    print("Boundary: loopback-only, allowlisted workflows, no arbitrary shell execution.", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _program_status_or_governance(root: Path) -> dict[str, Any]:
    try:
        return program_status(root)
    except (FileNotFoundError, KeyError, ValueError):
        audit = audit_governance(root)
        return {
            "status": audit.get("status", "UNKNOWN"),
            "governance": audit.get("finalizationReadiness", {}),
            "nextAction": "Configure or bind the existing backlog authority before generation.",
        }


def _repository_root(value: str | Path) -> Path:
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Repository root does not exist: {root}")
    return root


def _git(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _clean_text(value: Any, *, maximum: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("Text inputs must be strings")
    return " ".join(value.split())[:maximum]
